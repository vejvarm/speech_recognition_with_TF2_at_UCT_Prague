import os
import time

import tensorflow as tf

from typing import Tuple, List

from autocorrect import Speller
from matplotlib import pyplot as plt
from tensorflow.keras.layers import Layer, Embedding, InputLayer, Reshape, Conv2D, Dropout, BatchNormalization, GRU, Bidirectional, Dense, ReLU, Permute, Lambda
from tensorflow.keras import backend as K

from DataOps import load_and_preprocess_lm_dataset
from DigitOps import DigitTranscriber
from FLAGS import FLAGS


LOGGER = FLAGS.logger

# custom trained autocorrect model for czech language
SPELL = Speller('cs', fast=False, threshold=2)
DT = DigitTranscriber()


class GRULanguageModel(Layer):
    GruUnits = Tuple[int, ...]
    DropRates = List

    def __init__(self, vocab_size: int, gru_units: GruUnits, batch_norm: bool, bn_momentum: float, drop_rates: DropRates,
                 name="language_model", dtype=float, trainable=True):
        """ Simple language model which takes AM output and returns output of same shape

        :param vocab_size (int): size of the input vocabulary
        :param gru_units (Tuple[int, ...]): sizes of the GRU hidden units (len represents number of gru layers)
        :param batch_norm (bool): whether to use batch normalization after each layer
        :param bn_momentum (float): momentum of batch_normalization layers (unused if batch_norm==False)
        :param drop_rates List[float, ...]: drop rates for Dropout layers after each BGRU layer
        """
        super(GRULanguageModel, self).__init__(name=name, dtype=dtype, trainable=trainable)

        self._name = name
        self._dtype = dtype
        self._trainable = trainable
        self._C = vocab_size     # character vocabulary size
        self._B = gru_units      # hidden sizes of BGRU layers
        self._D = drop_rates     # drop rates for embedding and bgru layers
        self._D.extend([0.]*(len(gru_units) - len(drop_rates)))  # extend empty dropout rates
        self.batch_norm = batch_norm
        self.bn_momentum = bn_momentum

        self.bgru = []
        self.bgru_bn = []
        self.bgru_dropouts = []

    def build(self, input_shape):
        self.inp = InputLayer(input_shape=input_shape)
        for size, drop in zip(self._B, self._D):
            self.bgru.append(Bidirectional(GRU(size, return_sequences=True)))
            if self.batch_norm:
                self.bgru_bn.append(BatchNormalization(momentum=self.bn_momentum))
            self.bgru_dropouts.append(Dropout(drop))
        self.dense = Dense(self._C)

    def call(self, x_input, training=None):
        x = self.inp(x_input)
        for i in range(0, len(self.bgru)):
            x = self.bgru[i](x)
            if self.batch_norm:
                x = self.bgru_bn[i](x)
            if training:
                x = self.bgru_dropouts[i](x)
        return self.dense(x)

    def get_config(self):
        config = {"name": self._name,
                  "trainable": self._trainable,
                  "dtype": self._dtype,
                  "vocab_size": self._C,
                  "gru_units": self._B,
                  "batch_norm": self.batch_norm,
                  "bn_momentum": self.bn_momentum,
                  "drop_rates": list(self._D)}
        return config


class EncoderLM(tf.keras.Model):

    def __init__(self, vocab_size=FLAGS.lm_enc_params['vocab_size'],
                 embedding_dim=FLAGS.lm_enc_params['embedding_dim'],
                 gru_dims=FLAGS.lm_enc_params['gru_dims']):
        super(EncoderLM, self).__init__()
        self.gru_dims = gru_dims
        use_cudnn = FLAGS.enc_dec_hyperparams["cuDNNGRU"]

        # embedding layer
        self.embedding = Embedding(vocab_size, embedding_dim, mask_zero=True)

        # GRU layers
        self.grus = list()
        for dims in gru_dims[:-1]:
            self.grus.append(GRU(dims, return_sequences=True, reset_after=use_cudnn))

        # final GRU layer
        self.grus.append(GRU(gru_dims[-1], return_sequences=True, return_state=True, reset_after=use_cudnn))

    def call(self, input_sequence):
        x = self.embedding(input_sequence)

        for gru in self.grus[:-1]:
            x = gru(x)

        output, final_state = self.grus[-1](x)

        return output, final_state


class DecoderLM(tf.keras.Model):

    def __init__(self, vocab_size=FLAGS.lm_dec_params['vocab_size'],
                 embedding_dim=FLAGS.lm_dec_params['embedding_dim'],
                 gru_dims=FLAGS.lm_dec_params['gru_dims']):
        super(DecoderLM, self).__init__()
        self.gru_dims = gru_dims
        use_cudnn = FLAGS.enc_dec_hyperparams["cuDNNGRU"]

        # embedding layer
        self.embedding = Embedding(vocab_size, embedding_dim, mask_zero=True)

        # GRU layers
        self.grus = list()
        for i, dims in enumerate(gru_dims[:-1]):
            self.grus.append(GRU(dims, return_sequences=True, return_state=True, reset_after=use_cudnn, name=f"gru_dec_{i}"))

        # Final GRU layer
        self.grus.append(GRU(gru_dims[-1], return_sequences=True, return_state=True, reset_after=use_cudnn, name=f"gru_dec_final"))

        # Dense layer output
        self.dense = Dense(vocab_size)

    def call(self, input_sequence, states_in):
        # call embedding layer
        x = self.embedding(input_sequence)

        # first GRU layer (initialized with state from encoder)
        x, first_state = self.grus[0](x, states_in[0])

        middle_states = []
        # call GRU layers
        for i, gru in enumerate(self.grus[1:-1]):
            x, states = gru(x, states_in[i+1])
            middle_states.append(states)

        # call final GRU layer
        x, final_state = self.grus[-1](x, states_in[-1])

        # call dense layer for logit outputs
        logits = self.dense(x)

        all_states = [first_state, *middle_states, final_state]

        return logits, all_states


def loss_func(targets, logits, padding_vals=FLAGS.label_pad_val_lm):
    crossentropy = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)

    # mask padding values
    mask = tf.math.not_equal(targets, padding_vals)
    mask = tf.cast(mask, dtype=tf.int64)

    # calculate crossentropy loss value
    loss = crossentropy(targets, logits, sample_weight=mask)

    return loss


def accuracy_func(y_true, y_pred, padding_vals=FLAGS.label_pad_val_lm, pad_lengths=False):
    """ custom accuracy function based on number of correct classes vs total number of classes (true sentence length)

    :param y_true: true values [batch_size, sequence_length]
    :param y_pred: predicted values [batch_size, sequence_length, vocab_size]
    :param padding_vals: values which represent padding (default: -1)
    :param pad_lengths: if we want to pad values (useful during test mode)
    :return: accuracy based on number of correct chracters/words divided by total length of the true sentence
    """
    pred_values = K.cast(K.argmax(y_pred, axis=-1), dtype=tf.int32)

    if pad_lengths:
        true_len = y_true.shape[1]
        pred_len = y_pred.shape[1]
        # padding for longer/shorter results than correct values
        if true_len - pred_len > 0:
            pred_values = tf.pad(pred_values, [[0, 0], [0, true_len - pred_len]], constant_values=100000)
        elif true_len - pred_len < 0:
            y_true = tf.pad(y_true, [[0, 0], [0, pred_len - true_len]], constant_values=100000)

    correct = K.cast(K.equal(y_true, pred_values), dtype=tf.float32)
    # don't include padding values in accuracy calculations
    mask = K.cast(K.greater(y_true, padding_vals), dtype=tf.float32)
    n_correct = K.sum(mask*correct)
    n_total = K.sum(mask)

    acc = n_correct/n_total

    return acc


# Use the @tf.function decorator to take advance of static graph computation
@tf.function(experimental_relax_shapes=True)
def train_step(encoder, decoder, input_seq, target_seq_in, target_seq_out, optimizer):
    """ A training step, train a batch of the data and return the loss value reached
        Input:
        - input_seq: array of integers, shape [batch_size, max_seq_len, embedding dim].
            the input sequence
        - target_seq_out: array of integers, shape [batch_size, max_seq_len, embedding dim].
            the target seq, our target sequence
        - target_seq_in: array of integers, shape [batch_size, max_seq_len, embedding dim].
            the input sequence to the decoder, we use Teacher Forcing
        - optimizer: a tf.keras.optimizers.
        Output:
        - loss: loss value

    """
    # Network’s computations need to be put under tf.GradientTape() to keep track of gradients
    with tf.GradientTape() as tape:
        # Get the encoder outputs
        en_outputs = encoder(input_seq)
        # Set the encoder and decoder states
        en_states = en_outputs[1:]
        de_states = [en_states, None, None]
        # Get the decoder outputs
        logits, de_states_new = decoder(target_seq_in, de_states)
        # Calculate the loss function
        loss = loss_func(target_seq_out, logits)
    acc = accuracy_func(target_seq_out, logits)

    variables = encoder.trainable_variables + decoder.trainable_variables
    # Calculate the gradients for the variables
    gradients = tape.gradient(loss, variables)
    # Apply the gradients and update the optimizer
    optimizer.apply_gradients(zip(gradients, variables))

    return loss, acc


def test_step(encoder, decoder, input_seq, target_seq_out, min_len=2):
    """

    :param encoder:
    :param decoder:
    :param input_seq:
    :param target_seq_out:
    :param min_len:
    :return:
    """

    if input_seq.shape[1] < min_len:
        return tf.constant(0.5)
    else:
        # Get the encoder outputs
        en_outputs = encoder(input_seq)
        # Set the encoder and decoder states
        en_states = en_outputs[1:]
        de_states = [en_states, None, None]

        # Create initial decoder inputs for the batch:
        de_inputs = tf.ones((tf.shape(input_seq)[0], 1), tf.int32)*FLAGS.c2n_map_lm["<sos>"]

        full_outputs = None
        while True:
            # Decode and get the output probabilities
            de_outputs, de_states = decoder(de_inputs, de_states)

            if full_outputs is None:
                full_outputs = de_outputs
            else:
                full_outputs = tf.concat([full_outputs, de_outputs], 1)
            de_inputs = tf.argmax(de_outputs, -1)
            last_class = de_inputs[0, -1]

            if tf.equal(last_class, FLAGS.c2n_map_lm['<eos>']) or full_outputs.shape[1] >= FLAGS.enc_dec_hyperparams["max_length"]:
                accuracy = accuracy_func(target_seq_out, full_outputs, pad_lengths=True)
                break

        return accuracy


# Create the main train function
def main_train(encoder, decoder, train_ds, test_ds, n_epochs, optimizer, checkpoint, checkpoint_prefix):
    losses = []
    accuracies = []
    test_accuracies = []
    epoch_mean_test_accuracy = [0., ]

    for e in range(n_epochs):
        print(f"EPOCH {e}")
        # Get the initial time
        start = time.time()

        # For every batch of training data
        print("Train Dataset")
        accuracy_sum = 0.
        for batch, (input_seq, target_seq_in, target_seq_out) in enumerate(train_ds):
            # Train and get the loss value
            loss, accuracy = train_step(encoder, decoder, input_seq, target_seq_in, target_seq_out, optimizer)

            accuracy_sum += accuracy.numpy()

            if batch % 100 == 0:
                # Store the loss and accuracy values
                losses.append(loss)
                accuracies.append(accuracy_sum/(batch+1))
                print('Batch {} Loss {:.4f} Acc:{:.4f}'.format(batch, loss.numpy(), accuracies[-1]))

        # For testing data
        if test_ds:
            accuracy_sum = 0.
            print("Test Dataset")
            for batch, (input_seq, _, target_seq_out) in enumerate(test_ds):
                accuracy = test_step(encoder, decoder, input_seq, target_seq_out)

                accuracy_sum += accuracy.numpy()

                if batch % 100 == 0:
                    test_accuracies.append(accuracy_sum / (batch + 1))
                    print('Batch {} Acc:{:.4f}'.format(batch, test_accuracies[-1]))

            epoch_mean_test_accuracy.append(tf.reduce_mean(test_accuracies).numpy())
            print(f"Mean test accuracy {epoch_mean_test_accuracy[-1]}")

            # saving (checkpoint) of the model if it fares better than in the last epoch
            if epoch_mean_test_accuracy[-1] > epoch_mean_test_accuracy[-2]:
                checkpoint.save(file_prefix=checkpoint_prefix)
        else:
            # save checkpoint blindly every 2 epochs
            if (e + 1) % 2 == 0:
                checkpoint.save(file_prefix=checkpoint_prefix)

        print('Time taken for 1 epoch {:.4f} sec\n'.format(time.time() - start))

    return losses, accuracies, test_accuracies, epoch_mean_test_accuracy


def run_lm_training(encoder, decoder, train_ds, test_ds, epochs=FLAGS.enc_dec_hyperparams['epochs']):
    """

    :param encoder:
    :param decoder:
    :param train_ds:
    :param test_ds:
    :param epochs:
    :return:
    """
    optimizer = tf.keras.optimizers.Adam(lr=FLAGS.enc_dec_hyperparams['lr'],
                                         clipnorm=FLAGS.enc_dec_hyperparams['clipnorm'])
    # create checkpoint object for saving the model
    checkpoint_dir = FLAGS.enc_dec_hyperparams['checkpoint_dir']
    checkpoint_prefix = os.path.join(checkpoint_dir, "ckpt")
    checkpoint = tf.train.Checkpoint(optimizer=optimizer,
                                     encoder=encoder,
                                     decoder=decoder)

    losses, accuracies, test_accuracies, epoch_mean_test_accuracy = main_train(encoder, decoder,
                                                                               train_ds, test_ds,
                                                                               epochs, optimizer,
                                                                               checkpoint, checkpoint_prefix)

    return losses, accuracies, test_accuracies, epoch_mean_test_accuracy


def check_enc_dec_lm(vocab_size=4, embedding_dim=16, encoder_gru_dims=(16, 8), decoder_gru_dims=(8, 4)):
    """ check functionality of EncoderLM DecoderLM models

    :param vocab_size: size of the input/output vocabulary
    :param embedding_dim: dimensionality of the embedding vectors
    :param encoder_gru_dims: dimensions of the gru layers in EncoderLM
    :param decoder_gru_dims: dimensions of the gru layers in DecoderLM
    """
    vocab_size = vocab_size + 1
    # Create the encoder
    encoder = EncoderLM(vocab_size, embedding_dim, encoder_gru_dims)
    # Call the encoder for testing
    test_encoder_output = encoder(tf.constant([[1, 3, 2, 1, 0, 0]]))
    LOGGER.info(test_encoder_output[0].shape)
    # Create the decoder
    decoder = DecoderLM(vocab_size, embedding_dim, decoder_gru_dims)
    # Get the initial states
    de_initial_state = test_encoder_output[1:]
    # Call the decoder for testing
    test_decoder_output = decoder(tf.constant([[1, 3, 4, 1, 2, 0, 0, 0]]), de_initial_state)
    LOGGER.info(test_decoder_output[0].shape)


if __name__ == '__main__':
    physical_devices = tf.config.list_physical_devices('GPU')
    tf.config.experimental.set_memory_growth(physical_devices[0], True)
    # check_enc_dec_lm()

    # initialize encoder and decoder models with default params from FLAGS
    encoder = EncoderLM()
    decoder = DecoderLM()

    # load datasets
    train_dataset_path = FLAGS.enc_dec_hyperparams['train_dataset_path']
    ds_train = load_and_preprocess_lm_dataset((train_dataset_path, ))
    test_dataset_path = FLAGS.enc_dec_hyperparams['test_dataset_path']
    ds_test = load_and_preprocess_lm_dataset((test_dataset_path, ), batch_size=1)

    # run training on training dataset
    losses, accuracies, test_accuracies, epoch_mean_test_accuracy = run_lm_training(encoder, decoder, ds_train, ds_test)

    # plot results
    plt.figure()
    plt.plot(losses)
    plt.title("Training Loss")
    plt.xlabel("100s of batches")
    plt.ylabel("loss")

    plt.figure()
    plt.plot(accuracies)
    plt.title("Training Accuracy")
    plt.xlabel("100s of batches")
    plt.ylabel("accuracy")

    plt.show()

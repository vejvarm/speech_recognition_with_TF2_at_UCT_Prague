import tensorflow as tf


class FLAGS:
    c2n_map = {'a': 0, 'á': 1, 'b': 2, 'c': 3, 'č': 4, 'd': 5, 'ď': 6, 'e': 7, 'é': 8, 'ě': 9,
               'f': 10, 'g': 11, 'h': 12, 'ch': 13, 'i': 14, 'í': 15, 'j': 16, 'k': 17, 'l': 18, 'm': 19,
               'n': 20, 'ň': 21, 'o': 22, 'ó': 23, 'p': 24, 'q': 25, 'r': 26, 'ř': 27, 's': 28, 'š': 29,
               't': 30, 'ť': 31, 'u': 32, 'ú': 33, 'ů': 34, 'v': 35, 'w': 36, 'x': 37, 'y': 38, 'ý': 39,
               'z': 40, 'ž': 41, ' ': 42}
    n2c_map = {val: idx for idx, val in c2n_map.items()}
    alphabet_size = len(c2n_map)

    # load_dir = "b:/!temp/PDTSC_Debug/"
    load_dir = "g:/datasets/PDTSC_MFSC_unigram_40_banks_min_100_max_3000_tfrecord"
    # load_dir = "g:/datasets/ORAL_MFSC_unigram_40_banks_min_100_max_3000_tfrecord"
    # load_dir = "g:/datasets/ORAL_08"
    save_dir = "./results/"
    checkpoint_path = None

    num_runs = 5
    max_epochs = 50
    batch_size_per_GPU = 8

    #    num_data = 391216
    num_train_data = int(48812/2)  # int(11308/2)  # full ORAL == 374714/2
    num_test_data = int(4796/2)  # int(1304/2)  # full ORAL == 16502/2
    num_features = 123
    min_time = 100
    max_time = 3000  # TODO: change back to 3000 when including PDTSC
    buffer_size = int(0.1*num_train_data/batch_size_per_GPU)
    shuffle_seed = 42

    num_cpu_cores = tf.data.experimental.AUTOTUNE

    bucket_width = 100

    feature_pad_val = 0.0
    label_pad_val = -1

    # MODEL
    save_architecture_image = True
    show_shapes = True

    weight_init_mean = 0.0
    weight_init_stddev = 0.0001

    ff_first_params = {
        'use': False,
        'num_units': [128, 64],
        'batch_norm': False,
        'drop_rates': [0.],
    }
    conv_params = {
        'use': True,
        'channels': [32, 64],
        'kernels': [(16, 32), (8, 16)],
        'strides': [(2, 4), (2, 4)],
        'dilation_rates': [(1, 1), (1, 1)],
        'padding': 'same',
        'data_format': 'channels_last',
        'batch_norm': True,
        'drop_rates': [0., 0.],
    }
    bn_momentum = 0.9
    relu_clip_val = 20
    relu_alpha = 0.2
    rnn_params = {
        'use': True,
        'num_units': [128],
        'batch_norm': True,
        'drop_rates': [0.],
    }
    ff_params = {
        'use': True,
        'num_units': [64],
        'batch_norm': True,
        'drop_rates': [0.],
    }

    # Optimizer
    lr = 0.1
    lr_decay = True
    lr_decay_rate = 0.5
    lr_decay_epochs = 1
    epsilon = 0.1
    amsgrad = True

    # Decoder
    beam_width = 256
    top_paths = 1  # > 1 not implemented

    # Early stopping
    patience_epochs = 3


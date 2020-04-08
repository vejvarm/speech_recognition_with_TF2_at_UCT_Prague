# Character-level DNN Model for Czech Language Speech Recognition using TensorFlow 2

A project which was given birth as a masters thesis at UCT Prague and now continues as a part of my PhD studies. 
The core concept is developing a Character-level deep neural network (DNN) based model for 
automatic speech recognition (ASR) and transcription of Czech naturally spoken language. 
Ultimately the transcription is then to be used for controlling a robotic system using natural Czech spoken language, 
utilizing keyword spotting mechanisms.

The system starts with a data transformation pipeline, which feeds
preprocessed speech data from two Czech natural speech corpuses ([PDTSC 1.0](https://ufal.mff.cuni.cz/pdtsc1.0/en/index.html) and [ORAL2013](https://wiki.korpus.cz/doku.php/en:cnk:oral2013)) into an Acoustic Model (AM).
Data Augmentation techniques, such as [SpecAugment](https://arxiv.org/abs/1904.08779) are implemented into the pipeline for improving performance on testing dataset.

## Table of contents
* [Getting Started](#getting-started)
    * [Requirements](#requirements)
    * [Preparing datasets for training](#preparing-datasets-for-training)
* [Project status](#project-status)
* [Built With](#built-with)
* [Contributing](#contributing)
* [Versioning](#versioning)
* [Authors](#authors)
* [License](#license)
* [Acknowledgments](#acknowledgments)

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Requirements

The environment was created and the required packaged were installed using the [Anaconda](https://www.anaconda.com) 
Python library management platform which can be downloaded from [Anaconda Distribution](https://www.anaconda.com/distribution/).

You can recreate the environment with all the required packages using the 
[environment.yml](https://github.com/vejvarm/speech_recognition_with_TF2_at_UCT_Prague/blob/master/environment.yml) 
file in this repository by following instructions from [conda documentation](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#creating-an-environment-from-an-environment-yml-file).

Once conda is installed, all you have to do is open Anaconda Prompt and input:
```
conda env create -f environment.yml
```

### Preparing datasets for training
In order to train the network, you need to have a speech dataset. 
In this project, training was done on aforementioned [PDTSC 1.0](https://ufal.mff.cuni.cz/pdtsc1.0/en/index.html)
and [ORAL2013](https://wiki.korpus.cz/doku.php/en:cnk:oral2013) datasets. 
For these to work, they need to be preprocessed and transformed into MFCC/MFSC feature structures of correct shape,
which is done through the following steps:

1. 
2.

## Project status

Currently the project is in the Data Augmentation implementation and testing stages.

## Contributing

Please read [CONTRIBUTING.md](https://gist.github.com/PurpleBooth/b24679402957c63ec426) for details on our code of conduct, and the process for submitting pull requests to us.

## Versioning

We use [SemVer](http://semver.org/) for versioning. For the versions available, see the [tags on this repository](https://github.com/vejvarm/speech_recognition_with_TF2_at_UCT_Prague/tags). 

## Authors

* **Martin Vejvar** - *Core developer* - [vejvarm](https://github.com/vejvarm)

See also the list of [contributors](https://github.com/vejvarm/speech_recognition_with_TF2_at_UCT_Prague/contributors) who participated in this project.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details

## Acknowledgments
* [How to write a good README for your GitHub project](https://bulldogjob.com/news/449-how-to-write-a-good-readme-for-your-github-project)
* [A template to make good README.md](https://gist.github.com/PurpleBooth/109311bb0361f32d87a2#file-readme-template-md)



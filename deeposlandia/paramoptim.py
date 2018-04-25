"""Main method to train neural networks with Keras API
"""

import argparse
import itertools
import os
import sys
import numpy as np

from datetime import datetime

from keras import backend, callbacks
from keras.models import Model
from keras.optimizers import Adam

from deeposlandia import generator, utils
from deeposlandia.keras_feature_detection import FeatureDetectionNetwork
from deeposlandia.keras_semantic_segmentation import SemanticSegmentationNetwork

SEED = int(datetime.now().timestamp())

def add_instance_arguments(parser):
    """Add instance-specific arguments from the command line

    Parameters
    ----------
    parser : argparse.ArgumentParser
        Input parser

    Returns
    -------
    argparse.ArgumentParser
        Modified parser, with additional arguments
    """
    parser.add_argument('-a', '--aggregate-label', action='store_true',
                        help="Aggregate labels with respect to their categories")
    parser.add_argument('-D', '--dataset',
                        required=True,
                        help="Dataset type (either mapillary or shapes)")
    parser.add_argument('-M', '--model',
                        default="feature_detection",
                        help=("Type of model to train, either "
                              "'feature_detection' or 'semantic_segmentation'"))
    parser.add_argument('-n', '--name',
                        default="cnn",
                        help=("Model name that will be used for results, "
                              "checkout and graph storage on file system"))
    parser.add_argument('-p', '--datapath',
                        default="./data",
                        help="Relative path towards data directory")
    parser.add_argument('-s', '--image-size',
                        default=224,
                        type=int,
                        help=("Desired size of images (width = height)"))
    return parser

def add_hyperparameters(parser):
    """Add hyperparameter arguments from the command line

    Parameters
    ----------
    parser : argparse.ArgumentParser
        Input parser

    Returns
    -------
    argparse.ArgumentParser
        Modified parser, with additional arguments
    """
    parser.add_argument('-b', '--batch-size',
                        type=int,
                        default=50,
                        help=("Number of images that must be contained "
                              "into a single batch"))
    parser.add_argument('-d', '--dropout',
                        type=float, nargs='+',
                        default=[0.5, 0.75, 1.0],
                        help=("Percentage of dropped out neurons "
                              "during training"))
    parser.add_argument('-L', '--learning-rate',
                        default=[0.01, 0.001, 0.0001],
                        type=float, nargs="+",
                        help=("List of learning rate components (starting LR, "
                              "decay steps and decay rate)"))
    parser.add_argument('-l', '--learning-rate-decay',
                        default=[0.001, 0.0001, 0.00001],
                        type=float, nargs="+",
                        help=("List of learning rate components (starting LR, "
                              "decay steps and decay rate)"))
    parser.add_argument('-N', '--network', nargs='+',
                        default=['simple', 'vgg16'],
                        help=("Neural network size, either 'simple', 'vgg' or "
                              "'inception' ('simple' refers to 3 conv/pool "
                              "blocks and 1 fully-connected layer; the others "
                              "refer to state-of-the-art networks)"))
    return parser

def add_training_arguments(parser):
    """Add training-specific arguments from the command line

    Parameters
    ----------
    parser : argparse.ArgumentParser
        Input parser

    Returns
    -------
    argparse.ArgumentParser
        Modified parser, with additional arguments
    """
    parser.add_argument('-e', '--nb-epochs',
                        type=int,
                        default=0,
                        help=("Number of training epochs (one epoch means "
                              "scanning each training image once)"))
    parser.add_argument('-ii', '--nb-testing-image',
                        type=int,
                        default=5000,
                        help=("Number of training images"))
    parser.add_argument('-it', '--nb-training-image',
                        type=int,
                        default=18000,
                        help=("Number of training images"))
    parser.add_argument('-iv', '--nb-validation-image',
                        type=int,
                        default=2000,
                        help=("Number of validation images"))
    return parser

def get_data(folders, dataset, model, image_size, batch_size):
    """
    """
    # Data gathering
    if (os.path.isfile(folders["training_config"]) and os.path.isfile(folders["validation_config"])
        and os.path.isfile(folders["testing_config"])):
        train_config = utils.read_config(folders["training_config"])
        label_ids = [x['id'] for x in train_config['labels'] if x['is_evaluate']]
        train_generator = generator.create_generator(
            dataset,
            model,
            folders["prepro_training"],
            image_size,
            batch_size,
            label_ids,
            seed=SEED)
        validation_generator = generator.create_generator(
            dataset,
            model,
            folders["prepro_validation"],
            image_size,
            batch_size,
            label_ids,
            seed=SEED)
        test_generator = generator.create_generator(
            dataset,
            model,
            folders["prepro_testing"],
            image_size,
            batch_size,
            label_ids,
            inference=True,
            seed=SEED)
    else:
        utils.logger.error(("There is no valid data with the specified parameters. "
                           "Please generate a valid dataset before calling the training program."))
        sys.exit(1)
    nb_labels = len(label_ids)
    return nb_labels, train_generator, validation_generator, test_generator

def run_model(train_generator, validation_generator,
              instance_name, image_size, nb_labels, nb_training_image, nb_validation_image,
              batch_size, dropout, learning_rate, learning_rate_decay, network):
    """
    """
    if args.model == "feature_detection":
        net = FeatureDetectionNetwork(network_name=instance_name,
                                      image_size=image_size,
                                      nb_channels=3,
                                      nb_labels=nb_labels,
                                      architecture=network)
        loss_function = "binary_crossentropy"
    elif args.model == "semantic_segmentation":
        net = SemanticSegmentationNetwork(network_name=instance_name,
                                          image_size=image_size,
                                          nb_channels=3,
                                          nb_labels=nb_labels,
                                          architecture=network)
        loss_function = "categorical_crossentropy"
    else:
        utils.logger.error(("Unrecognized model. Please enter 'feature_detection' "
                            "or 'semantic_segmentation'."))
        sys.exit(1)
    model = Model(net.X, net.Y)
    opt = Adam(lr=learning_rate, decay=learning_rate_decay)
    model.compile(loss=loss_function, optimizer=opt, metrics=['acc'])

    # Model training
    STEPS = nb_training_image // batch_size
    VAL_STEPS = nb_validation_image // batch_size
    hist = model.fit_generator(train_generator,
                               epochs=args.nb_epochs,
                               steps_per_epoch=STEPS,
                               validation_data=validation_generator,
                               validation_steps=VAL_STEPS)
    ref_metric = max(hist.history['val_acc'])
    return {'model': model, 'val_acc': ref_metric,
            'batch_size': batch_size, 'network': network, 'dropout': dropout,
            'learning_rate': learning_rate, 'learning_rate_decay': learning_rate_decay}

if __name__=='__main__':
    """Main method: run a convolutional neural network using Keras API
    """

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description=("Convolutional Neural Netw"
                                                  "ork on street-scene images:"
                                                  " hyper-parameter "
                                                  "optimization"))
    parser = add_instance_arguments(parser)
    parser = add_hyperparameters(parser)
    parser = add_training_arguments(parser)
    args = parser.parse_args()

    # Instance name (name + image size + network size + batch_size
    # + aggregate? + dropout + learning_rate)
    aggregate_value = "full" if not args.aggregate_label else "aggregated"
    instance_args = [args.name, args.image_size, args.network, args.batch_size,
                     aggregate_value, args.dropout, utils.list_to_str(args.learning_rate)]
    instance_name = utils.list_to_str(instance_args, "_")

    # Data path and repository management
    folders = utils.prepare_folders(args.datapath, args.dataset, aggregate_value,
                                    args.image_size, args.model)

    utils.logger.info(folders)
    utils.logger.info(args.batch_size)
    utils.logger.info(args.dropout)
    utils.logger.info(args.learning_rate)
    utils.logger.info(args.learning_rate_decay)
    utils.logger.info(args.network)

    nb_labels, train_gen, valid_gen, test_gen = get_data(folders, args.dataset, args.model,
                                                         args.image_size, args.batch_size)

    for parameters in itertools.product(args.dropout, args.learning_rate, args.learning_rate_decay,
                                        args.network):
        print(*parameters)
        model_output = run_model(train_gen, valid_gen, instance_name, args.image_size, nb_labels,
                                 args.nb_training_image, args.nb_validation_image, args.batch_size,
                                 *parameters)

    print(model_output)

    backend.clear_session()

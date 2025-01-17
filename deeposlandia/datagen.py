"""Main method to generate new datasets

Example of program calls:

* generate 64*64 pixel images from Shapes dataset, 10000 images in the training
  set, 100 in the validation set, 1000 in the testing set::

    python deeposlandia/datagen.py -D shapes -s 64 -t 10000 -v 100 -T 1000

* generate 224*224 pixel images from Mapillary dataset, with aggregated
  labels::

    python deeposlandia/datagen.py -D mapillary -s 224 -a

"""

import argparse
import os
import sys

import daiquiri
import pandas as pd

from deeposlandia import config, utils
from deeposlandia.datasets import AVAILABLE_DATASETS
from deeposlandia.datasets.mapillary import MapillaryDataset
from deeposlandia.datasets.aerial import AerialDataset
from deeposlandia.datasets.shapes import ShapeDataset
from deeposlandia.datasets.tanzania import TanzaniaDataset


logger = daiquiri.getLogger(__name__)


def main(args):
    # Data path and repository management
    aggregate_value = "full" if not args.aggregate_label else "aggregated"
    input_folder = utils.prepare_input_folder(args.datapath, args.dataset)
    prepro_folder = utils.prepare_preprocessed_folder(
        args.datapath, args.dataset, args.image_size, aggregate_value
    )

    # Dataset creation
    if args.dataset == "mapillary":
        config_name = (
            "config.json"
            if not args.aggregate_label
            else "config_aggregate.json"
        )
        config_path = os.path.join(input_folder, config_name)
        train_dataset = MapillaryDataset(args.image_size, config_path)
        validation_dataset = MapillaryDataset(args.image_size, config_path)
        test_dataset = MapillaryDataset(args.image_size, config_path)
    elif args.dataset == "shapes":
        train_dataset = ShapeDataset(args.image_size)
        validation_dataset = ShapeDataset(args.image_size)
        test_dataset = ShapeDataset(args.image_size)
        os.makedirs(
            os.path.join(prepro_folder["testing"], "labels"), exist_ok=True
        )
    elif args.dataset == "aerial":
        train_dataset = AerialDataset(args.image_size)
        validation_dataset = AerialDataset(args.image_size)
        test_dataset = AerialDataset(args.image_size)
    elif args.dataset == "tanzania":
        train_dataset = TanzaniaDataset(args.image_size)
        validation_dataset = TanzaniaDataset(args.image_size)
        test_dataset = TanzaniaDataset(args.image_size)
    else:
        logger.error(
            "Unsupported dataset type. Please choose amongst %s",
            AVAILABLE_DATASETS,
        )
        sys.exit(1)

    # Dataset populating/loading
    # (depends on the existence of a specification file)
    if args.nb_training_image > 0:
        if os.path.isfile(prepro_folder["training_config"]):
            train_dataset.load(
                prepro_folder["training_config"], args.nb_training_image
            )
        else:
            logger.info(
                (
                    "No existing configuration file for this dataset. "
                    "Create %s.",
                    prepro_folder["training_config"],
                )
            )
            input_image_dir = os.path.join(input_folder, "training")
            train_dataset.populate(
                prepro_folder["training"],
                input_image_dir,
                nb_images=args.nb_training_image,
                aggregate=args.aggregate_label,
                nb_processes=int(config.get("running", "processes")),
            )
            train_dataset.save(prepro_folder["training_config"])

    if args.nb_validation_image > 0:
        if os.path.isfile(prepro_folder["validation_config"]):
            validation_dataset.load(
                prepro_folder["validation_config"], args.nb_validation_image
            )
        else:
            logger.info(
                (
                    "No existing configuration file for this dataset. "
                    "Create %s.",
                    prepro_folder["validation_config"],
                )
            )
            input_image_dir = os.path.join(input_folder, "validation")
            validation_dataset.populate(
                prepro_folder["validation"],
                input_image_dir,
                nb_images=args.nb_validation_image,
                aggregate=args.aggregate_label,
                nb_processes=int(config.get("running", "processes")),
            )
            validation_dataset.save(prepro_folder["validation_config"])

    if args.nb_testing_image > 0:
        if os.path.isfile(prepro_folder["testing_config"]):
            test_dataset.load(
                prepro_folder["testing_config"], args.nb_testing_image
            )
        else:
            logger.info(
                (
                    "No existing configuration file for this dataset. "
                    "Create %s.",
                    prepro_folder["testing_config"],
                )
            )
            input_image_dir = os.path.join(input_folder, "testing")
            test_dataset.populate(
                prepro_folder["testing"],
                input_image_dir,
                nb_images=args.nb_testing_image,
                aggregate=args.aggregate_label,
                labelling=False,
                nb_processes=int(config.get("running", "processes")),
            )
            test_dataset.save(prepro_folder["testing_config"])

    glossary = pd.DataFrame(train_dataset.labels)
    glossary["popularity"] = train_dataset.get_label_popularity()
    logger.info("Data glossary:\n%s", glossary)
    sys.exit(0)

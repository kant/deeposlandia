"""Flask web application for deeposlandia
"""

import daiquiri
from flask import (
    abort,
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
)
import json
import numpy as np
import os
import sys
from PIL import Image
from werkzeug.utils import secure_filename

from deeposlandia import config, utils
from deeposlandia.inference import predict


logger = daiquiri.getLogger(__name__)


PROJECT_FOLDER = config.get("folder", "project_folder")
UPLOAD_FOLDER = os.path.join(PROJECT_FOLDER, "uploads/")
PREDICT_FOLDER = os.path.join(PROJECT_FOLDER, "predicted/")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PREDICT_FOLDER, exist_ok=True)

if config.get("status", "status") == "dev":
    app = Flask(__name__)
elif config.get("status", "status") == "prod":
    app = Flask(__name__, static_folder=PROJECT_FOLDER)
else:
    logger.error("No defined status, please consider 'dev' or 'prod'.")
    sys.exit(1)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["ERROR_404_HELP"] = False

MODELS = ("feature_detection", "semantic_segmentation")
DATASETS = ("mapillary", "shapes", "aerial", "tanzania")
ALLOWED_EXTENSIONS = set(["png", "jpg", "jpeg", "tif"])


def check_model(model):
    """Check if `model` is valid, *i.e.* equal to `feature_detection` or
    `semantic_segmentation`

    Parameters
    ----------
    model : str
        String to verify
    """
    if model not in MODELS:
        abort(404, "Model {} not found".format(model))


def check_dataset(dataset):
    """Check if `dataset` is valid, *i.e.* equal to `shapes`,
    `mapillary`, `aerial` or `tanzania`

    Parameters
    ----------
    dataset : str
        String to verify
    """
    if dataset not in DATASETS:
        abort(404, "Dataset {} not found".format(dataset))


def allowed_file(filename):
    """Check if `filename` is really an image file name on the file system,
    *i.e.* composed of at least one '.' character, and which ends with an
    allowed extensions (namely, `jpg`, `jpeg` or `png`)

    Parameters
    ----------
    filename : str
        String to verify
    """
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def recover_image_info(dataset, filename):
    """Recover image full name on the application as well as corresponding
    ground-truth labels

    Parameters
    ----------
    dataset : str
    filename : str

    Returns
    -------
    dict
        Dictionary that contains image full names (raw images and labelled
    version) and label infos

    """
    dataset_code = dataset + "_agg" if dataset == "mapillary" else dataset
    image_file = os.path.join(dataset_code, "images", filename + ".png")
    label_file = image_file.replace("images", "labels")
    if dataset == "mapillary" or dataset == "mapillary_agg":
        image_file = image_file.replace(".png", ".jpg")
    server_label_filename = os.path.join(app.static_folder, label_file)
    server_label_image = np.array(Image.open(server_label_filename))
    if dataset == "mapillary":
        size_aggregation = "400_aggregated"
    elif dataset == "aerial":
        size_aggregation = "250_full"
    elif dataset == "tanzania":
        size_aggregation = "512_full"
    elif dataset == "shapes":
        size_aggregation = "64_full"
    else:
        raise ValueError(
            (
                "Unknown dataset. Please choose 'mapillary', "
                "'aerial', 'tanzania' or 'shapes'."
            )
        )
    with open(
        os.path.join(
            "data",
            dataset,
            "preprocessed",
            size_aggregation,
            "validation.json",
        )
    ) as fobj:
        config = json.load(fobj)
    if not dataset == "aerial":
        actual_labels = np.unique(
            server_label_image.reshape([-1, 3]), axis=0
        ).tolist()
    else:
        actual_labels = np.unique(server_label_image).tolist()
    printed_labels = [
        (item["category"], utils.GetHTMLColor(item["color"]))
        for item in config["labels"]
        if item["color"] in actual_labels
    ]
    return {
        "image_file": image_file,
        "label_file": label_file,
        "labels": printed_labels,
    }


@app.route("/")
def index():
    """Route to application home page

    Returns
    -------
    Jinja template
        Template for application home page
    """
    return render_template("index.html")


@app.route("/predictor_demo/<string:model>/<string:dataset>")
def demo_homepage(model, dataset):
    """Route to a demo page dedicated to `model` and ̀dataset`

    Parameters
    ----------
    model : str
        Considered research problem (either `feature_detection` or
    `semantic_segmentation`)
    dataset : str
        Considered dataset (either `shapes`, `mapillary`, `aerial` or
    `tanzania`)

    Returns
    -------
    Jinja template
        Template for demo web page fed with the specified model and an image
    filename
    """
    check_model(model)
    check_dataset(dataset)
    return render_template(
        dataset + "_demo.html",
        model=model,
        image_filename=os.path.join("sample_image", "raw_image.png"),
        label_filename=os.path.join("sample_image", "ground_truth.png"),
        ground_truth="",
        predicted_filename=os.path.join("sample_image", "prediction.png"),
        result="",
    )


@app.route("/predictor_demo/<string:model>/<string:dataset>/<string:image>")
def predictor_demo(model, dataset, image):
    """Route to a jsonified version of deep learning model predictions, for
    demo case

    Parameters
    ----------
    model : str
        Considered research problem (either `feature_detection` or
    `semantic_segmentation`)
    dataset : str
        Considered dataset (either `shapes` or `mapillary`)
    image : str
        Name of the demo image onto the server

    Returns
    -------
    dict
        Deep learning model prediction for demo page (depends on the chosen
    model, either feature detection or semantic segmentation)
    """
    agg_value = dataset == "mapillary"
    logger.info("file: %s, dataset: %s, model: %s", image, dataset, model)
    agg_value = dataset == "mapillary"
    image_info = recover_image_info(dataset, image)
    predictions = predict(
        [os.path.join(app.static_folder, image_info["image_file"])],
        dataset,
        model,
        aggregate=agg_value,
        output_dir=PREDICT_FOLDER,
    )
    if model == "feature_detection":
        predicted_image = "sample_image/prediction.png"
        predicted_labels = predictions[
            os.path.join(app.static_folder, image_info["image_file"])
        ]
    elif model == "semantic_segmentation":
        predicted_image = os.path.join(
            "predicted", image_info["label_file"].split("/")[-1]
        )
        predicted_labels = predictions["labels"]
    else:
        raise ValueError(
            (
                "Unknown model, please provide 'feature_detection'"
                "or 'semantic_segmentation'."
            )
        )
    return render_template(
        dataset + "_demo.html",
        model=model,
        image_filename=image_info["image_file"],
        label_filename=image_info["label_file"],
        ground_truth_labels=image_info["labels"],
        predicted_filename=predicted_image,
        predicted_labels=predicted_labels,
    )


@app.route("/prediction")
def prediction():
    """Route to a jsonified version of deep learning model predictions, for
    client tool

    Returns
    -------
    dict
        Deep learning model predictions
    """
    filename = os.path.basename(request.args.get("img"))
    filename = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    dataset = request.args.get("dataset")
    model = request.args.get("model")
    logger.info("file: %s, dataset: %s, model: %s", filename, dataset, model)
    predictions = predict(
        [filename],
        "mapillary",
        "semantic_segmentation",
        aggregate=True,
        output_dir=PREDICT_FOLDER,
    )
    return jsonify(predictions)


@app.route("/uploads/<filename>")
def send_image(filename):
    """Route to uploaded-by-client images

    Returns
    -------
    file
        Image file on the server (see Flask documentation)
    """
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/load_predictor")
def load_predictor():
    """
    """
    filename = os.path.join("sample_image", "ajaccio.png")
    return render_template("predictor.html", example_image=filename)


@app.route("/predictor", methods=["POST"])
def upload_image():
    """Route to deep learning predictor that takes as an input a
    uploaded-by-client image (which is saved on the server); if the uploaded
    file is not valid, the method does a simple redirection

    Returns
    -------
    Jinja template
        Template for predictor web page fed with the uploaded image

    """
    # check if the post request has the file part
    if "file" not in request.files:
        logger.info("No file part")
        return redirect(request.url)
    fobj = request.files["file"]
    # if user does not select file, browser also
    # submit a empty part without filename
    if fobj.filename == "":
        logger.info("No selected file")
        return redirect(request.url)
    if fobj and allowed_file(fobj.filename):
        message_info = ""
        filename = secure_filename(fobj.filename)
        full_filename = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        fobj.save(full_filename)
        target_size = 400
        image = Image.open(full_filename)
        image = image.resize((target_size, target_size))
        if image.mode == "RGBA":
            image = Image.merge(mode="RGB", bands=image.split()[:3])
            message_info = (
                "Warning: the uploaded image has an alpha channel "
                "(transparency feature). "
                "Here we use only RGB channels."
                )
            logger.warning(message_info)
        image.save(full_filename)
        return render_template(
            "predictor.html",
            image_name=filename,
            predicted_filename="sample_image/prediction.png",
            message=message_info
        )


@app.route("/demo_image_selector")
def demo_image_selector():
    """Route to a random server file with corresponding label information

    Returns
    -------
    dict
        Dictionary that contains four items: `image_name` is the short name of
    an image that will be displayed by the app, `image_file` is the relative
    path of the image on the server, `label_file` is the relative path of its
    labelled version on the server, and `labels` is a dictionary that
    summarizes the label information for displyaing purpose
    """
    dataset = request.args.get("dataset")
    dataset_code = dataset + "_agg" if dataset == "mapillary" else dataset
    server_folder = os.path.join(app.static_folder, dataset_code, "images")
    filename = np.random.choice(os.listdir(server_folder))
    return jsonify(image_name=filename.split(".")[0])

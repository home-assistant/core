"""Support for performing TensorFlow classification on images."""

from __future__ import annotations

import io
import logging
import os
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, UnidentifiedImageError
import tensorflow as tf
import voluptuous as vol

from homeassistant.components.image_processing import (
    CONF_CONFIDENCE,
    PLATFORM_SCHEMA as IMAGE_PROCESSING_PLATFORM_SCHEMA,
    ImageProcessingEntity,
)
from homeassistant.const import (
    CONF_ENTITY_ID,
    CONF_MODEL,
    CONF_NAME,
    CONF_SOURCE,
    EVENT_HOMEASSISTANT_START,
)
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import template
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.pil import draw_box

os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"

DOMAIN = "tensorflow"
_LOGGER = logging.getLogger(__name__)

ATTR_MATCHES = "matches"
ATTR_SUMMARY = "summary"
ATTR_TOTAL_MATCHES = "total_matches"
ATTR_PROCESS_TIME = "process_time"

CONF_AREA = "area"
CONF_BOTTOM = "bottom"
CONF_CATEGORIES = "categories"
CONF_CATEGORY = "category"
CONF_FILE_OUT = "file_out"
CONF_GRAPH = "graph"
CONF_LABELS = "labels"
CONF_LABEL_OFFSET = "label_offset"
CONF_LEFT = "left"
CONF_MODEL_DIR = "model_dir"
CONF_RIGHT = "right"
CONF_TOP = "top"

AREA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_BOTTOM, default=1): cv.small_float,
        vol.Optional(CONF_LEFT, default=0): cv.small_float,
        vol.Optional(CONF_RIGHT, default=1): cv.small_float,
        vol.Optional(CONF_TOP, default=0): cv.small_float,
    }
)

CATEGORY_SCHEMA = vol.Schema(
    {vol.Required(CONF_CATEGORY): cv.string, vol.Optional(CONF_AREA): AREA_SCHEMA}
)

PLATFORM_SCHEMA = IMAGE_PROCESSING_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_FILE_OUT, default=[]): vol.All(cv.ensure_list, [cv.template]),
        vol.Required(CONF_MODEL): vol.Schema(
            {
                vol.Required(CONF_GRAPH): cv.isdir,
                vol.Optional(CONF_AREA): AREA_SCHEMA,
                vol.Optional(CONF_CATEGORIES, default=[]): vol.All(
                    cv.ensure_list, [vol.Any(cv.string, CATEGORY_SCHEMA)]
                ),
                vol.Optional(CONF_LABELS): cv.isfile,
                vol.Optional(CONF_LABEL_OFFSET, default=1): int,
                vol.Optional(CONF_MODEL_DIR): cv.isdir,
            }
        ),
    }
)


def get_model_detection_function(model):
    """Get a tf.function for detection."""

    @tf.function
    def detect_fn(image):
        """Detect objects in image."""

        image, shapes = model.preprocess(image)
        prediction_dict = model.predict(image, shapes)
        return model.postprocess(prediction_dict, shapes)

    return detect_fn


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the TensorFlow image processing platform."""
    model_config = config[CONF_MODEL]
    model_dir = model_config.get(CONF_MODEL_DIR) or hass.config.path("tensorflow")
    labels = model_config.get(CONF_LABELS) or hass.config.path(
        "tensorflow", "object_detection", "data", "mscoco_label_map.pbtxt"
    )
    checkpoint = os.path.join(model_config[CONF_GRAPH], "checkpoint")
    pipeline_config = os.path.join(model_config[CONF_GRAPH], "pipeline.config")

    # Make sure locations exist
    if (
        not os.path.isdir(model_dir)
        or not os.path.isdir(checkpoint)
        or not os.path.exists(pipeline_config)
        or not os.path.exists(labels)
    ):
        _LOGGER.error("Unable to locate tensorflow model or label map")
        return

    # append custom model path to sys.path
    sys.path.append(model_dir)

    try:
        # Verify that the TensorFlow Object Detection API is pre-installed
        # These imports shouldn't be moved to the top, because they depend on code from the model_dir.
        # (The model_dir is created during the manual setup process. See integration docs.)

        # pylint: disable=import-outside-toplevel
        from object_detection.builders import model_builder
        from object_detection.utils import config_util, label_map_util
    except ImportError:
        _LOGGER.error(
            "No TensorFlow Object Detection library found! Install or compile "
            "for your system following instructions here: "
            "https://github.com/tensorflow/models/blob/master/research/object_detection/g3doc/tf2.md#installation"
        )
        return

    try:
        # Display warning that PIL will be used if no OpenCV is found.
        import cv2  # noqa: F401 pylint: disable=import-outside-toplevel
    except ImportError:
        _LOGGER.warning(
            "No OpenCV library found. TensorFlow will process image with "
            "PIL at reduced resolution"
        )

    hass.data[DOMAIN] = {CONF_MODEL: None}

    def tensorflow_hass_start(_event):
        """Set up TensorFlow model on hass start."""
        start = time.perf_counter()

        # Load pipeline config and build a detection model
        pipeline_configs = config_util.get_configs_from_pipeline_file(pipeline_config)
        detection_model = model_builder.build(
            model_config=pipeline_configs["model"], is_training=False
        )

        # Restore checkpoint
        ckpt = tf.compat.v2.train.Checkpoint(model=detection_model)
        ckpt.restore(os.path.join(checkpoint, "ckpt-0")).expect_partial()

        _LOGGER.debug(
            "Model checkpoint restore took %d seconds", time.perf_counter() - start
        )

        model = get_model_detection_function(detection_model)

        # Preload model cache with empty image tensor
        inp = np.zeros([2160, 3840, 3], dtype=np.uint8)
        # The input needs to be a tensor, convert it using `tf.convert_to_tensor`.
        input_tensor = tf.convert_to_tensor(inp, dtype=tf.float32)
        # The model expects a batch of images, so add an axis with `tf.newaxis`.
        input_tensor = input_tensor[tf.newaxis, ...]
        # Run inference
        model(input_tensor)

        _LOGGER.debug("Model load took %d seconds", time.perf_counter() - start)
        hass.data[DOMAIN][CONF_MODEL] = model

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, tensorflow_hass_start)

    category_index = label_map_util.create_category_index_from_labelmap(
        labels, use_display_name=True
    )

    add_entities(
        TensorFlowImageProcessor(
            hass,
            camera[CONF_ENTITY_ID],
            camera.get(CONF_NAME),
            category_index,
            config,
        )
        for camera in config[CONF_SOURCE]
    )


class TensorFlowImageProcessor(ImageProcessingEntity):
    """Representation of an TensorFlow image processor."""

    def __init__(
        self,
        hass,
        camera_entity,
        name,
        category_index,
        config,
    ):
        """Initialize the TensorFlow entity."""
        model_config = config.get(CONF_MODEL)
        self.hass = hass
        self._camera_entity = camera_entity
        if name:
            self._name = name
        else:
            self._name = f"TensorFlow {split_entity_id(camera_entity)[1]}"
        self._category_index = category_index
        self._min_confidence = config.get(CONF_CONFIDENCE)
        self._file_out = config.get(CONF_FILE_OUT)

        # handle categories and specific detection areas
        self._label_id_offset = model_config.get(CONF_LABEL_OFFSET)
        categories = model_config.get(CONF_CATEGORIES)
        self._include_categories = []
        self._category_areas = {}
        for category in categories:
            if isinstance(category, dict):
                category_name = category.get(CONF_CATEGORY)
                category_area = category.get(CONF_AREA)
                self._include_categories.append(category_name)
                self._category_areas[category_name] = [0, 0, 1, 1]
                if category_area:
                    self._category_areas[category_name] = [
                        category_area.get(CONF_TOP),
                        category_area.get(CONF_LEFT),
                        category_area.get(CONF_BOTTOM),
                        category_area.get(CONF_RIGHT),
                    ]
            else:
                self._include_categories.append(category)
                self._category_areas[category] = [0, 0, 1, 1]

        # Handle global detection area
        self._area = [0, 0, 1, 1]
        if area_config := model_config.get(CONF_AREA):
            self._area = [
                area_config.get(CONF_TOP),
                area_config.get(CONF_LEFT),
                area_config.get(CONF_BOTTOM),
                area_config.get(CONF_RIGHT),
            ]

        self._matches = {}
        self._total_matches = 0
        self._last_image = None
        self._process_time = 0

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera_entity

    @property
    def name(self):
        """Return the name of the image processor."""
        return self._name

    @property
    def state(self):
        """Return the state of the entity."""
        return self._total_matches

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return {
            ATTR_MATCHES: self._matches,
            ATTR_SUMMARY: {
                category: len(values) for category, values in self._matches.items()
            },
            ATTR_TOTAL_MATCHES: self._total_matches,
            ATTR_PROCESS_TIME: self._process_time,
        }

    def _save_image(self, image, matches, paths):
        img = Image.open(io.BytesIO(bytearray(image))).convert("RGB")
        img_width, img_height = img.size
        draw = ImageDraw.Draw(img)

        # Draw custom global region/area
        if self._area != [0, 0, 1, 1]:
            draw_box(
                draw, self._area, img_width, img_height, "Detection Area", (0, 255, 255)
            )

        for category, values in matches.items():
            # Draw custom category regions/areas
            if category in self._category_areas and self._category_areas[category] != [
                0,
                0,
                1,
                1,
            ]:
                label = f"{category.capitalize()} Detection Area"
                draw_box(
                    draw,
                    self._category_areas[category],
                    img_width,
                    img_height,
                    label,
                    (0, 255, 0),
                )

            # Draw detected objects
            for instance in values:
                label = "{} {:.1f}%".format(category, instance["score"])
                draw_box(
                    draw, instance["box"], img_width, img_height, label, (255, 255, 0)
                )

        for path in paths:
            _LOGGER.info("Saving results image to %s", path)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            img.save(path)

    def process_image(self, image):
        """Process the image."""
        if not (model := self.hass.data[DOMAIN][CONF_MODEL]):
            _LOGGER.debug("Model not yet ready")
            return

        start = time.perf_counter()
        try:
            import cv2  # pylint: disable=import-outside-toplevel

            img = cv2.imdecode(np.asarray(bytearray(image)), cv2.IMREAD_UNCHANGED)
            inp = img[:, :, [2, 1, 0]]  # BGR->RGB
            inp_expanded = inp.reshape(1, inp.shape[0], inp.shape[1], 3)
        except ImportError:
            try:
                img = Image.open(io.BytesIO(bytearray(image))).convert("RGB")
            except UnidentifiedImageError:
                _LOGGER.warning("Unable to process image, bad data")
                return
            img.thumbnail((460, 460), Image.ANTIALIAS)
            img_width, img_height = img.size
            inp = (
                np.array(img.getdata())
                .reshape((img_height, img_width, 3))
                .astype(np.uint8)
            )
            inp_expanded = np.expand_dims(inp, axis=0)

        # The input needs to be a tensor, convert it using `tf.convert_to_tensor`.
        input_tensor = tf.convert_to_tensor(inp_expanded, dtype=tf.float32)

        detections = model(input_tensor)
        boxes = detections["detection_boxes"][0].numpy()
        scores = detections["detection_scores"][0].numpy()
        classes = (
            detections["detection_classes"][0].numpy() + self._label_id_offset
        ).astype(int)

        matches = {}
        total_matches = 0
        for box, score, obj_class in zip(boxes, scores, classes, strict=False):
            score = score * 100
            boxes = box.tolist()

            # Exclude matches below min confidence value
            if score < self._min_confidence:
                continue

            # Exclude matches outside global area definition
            if (
                boxes[0] < self._area[0]
                or boxes[1] < self._area[1]
                or boxes[2] > self._area[2]
                or boxes[3] > self._area[3]
            ):
                continue

            category = self._category_index[obj_class]["name"]

            # Exclude unlisted categories
            if self._include_categories and category not in self._include_categories:
                continue

            # Exclude matches outside category specific area definition
            if self._category_areas and (
                boxes[0] < self._category_areas[category][0]
                or boxes[1] < self._category_areas[category][1]
                or boxes[2] > self._category_areas[category][2]
                or boxes[3] > self._category_areas[category][3]
            ):
                continue

            # If we got here, we should include it
            if category not in matches:
                matches[category] = []
            matches[category].append({"score": float(score), "box": boxes})
            total_matches += 1

        # Save Images
        if total_matches and self._file_out:
            paths = []
            for path_template in self._file_out:
                if isinstance(path_template, template.Template):
                    paths.append(
                        path_template.render(camera_entity=self._camera_entity)
                    )
                else:
                    paths.append(path_template)
            self._save_image(image, matches, paths)

        self._matches = matches
        self._total_matches = total_matches
        self._process_time = time.perf_counter() - start

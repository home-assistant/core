"""Support for OpenCV classification on images."""
from __future__ import annotations

from datetime import timedelta
import logging

import numpy as np
import requests
import voluptuous as vol

from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA,
    ImageProcessingEntity,
)
from homeassistant.const import CONF_ENTITY_ID, CONF_NAME, CONF_SOURCE
from homeassistant.core import HomeAssistant, split_entity_id
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

try:
    # Verify that the OpenCV python package is pre-installed
    import cv2

    CV2_IMPORTED = True
except ImportError:
    CV2_IMPORTED = False


_LOGGER = logging.getLogger(__name__)

ATTR_MATCHES = "matches"
ATTR_TOTAL_MATCHES = "total_matches"

CASCADE_URL = (
    "https://raw.githubusercontent.com/opencv/opencv/master/data/"
    "lbpcascades/lbpcascade_frontalface.xml"
)

CONF_CLASSIFIER = "classifier"
CONF_FILE = "file"
CONF_MIN_SIZE = "min_size"
CONF_NEIGHBORS = "neighbors"
CONF_SCALE = "scale"

DEFAULT_CLASSIFIER_PATH = "lbp_frontalface.xml"
DEFAULT_MIN_SIZE = (30, 30)
DEFAULT_NEIGHBORS = 4
DEFAULT_SCALE = 1.1
DEFAULT_TIMEOUT = 10

SCAN_INTERVAL = timedelta(seconds=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_CLASSIFIER): {
            cv.string: vol.Any(
                cv.isfile,
                vol.Schema(
                    {
                        vol.Required(CONF_FILE): cv.isfile,
                        vol.Optional(CONF_SCALE, DEFAULT_SCALE): float,
                        vol.Optional(
                            CONF_NEIGHBORS, DEFAULT_NEIGHBORS
                        ): cv.positive_int,
                        vol.Optional(CONF_MIN_SIZE, DEFAULT_MIN_SIZE): vol.Schema(
                            vol.All(vol.Coerce(tuple), vol.ExactSequence([int, int]))
                        ),
                    }
                ),
            )
        }
    }
)


def _create_processor_from_config(hass, camera_entity, config):
    """Create an OpenCV processor from configuration."""
    classifier_config = config.get(CONF_CLASSIFIER)
    name = f"{config[CONF_NAME]} {split_entity_id(camera_entity)[1].replace('_', ' ')}"

    processor = OpenCVImageProcessor(hass, camera_entity, name, classifier_config)

    return processor


def _get_default_classifier(dest_path):
    """Download the default OpenCV classifier."""
    _LOGGER.info("Downloading default classifier")
    req = requests.get(CASCADE_URL, stream=True, timeout=10)
    with open(dest_path, "wb") as fil:
        for chunk in req.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                fil.write(chunk)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the OpenCV image processing platform."""
    if not CV2_IMPORTED:
        _LOGGER.error(
            "No OpenCV library found! Install or compile for your system "
            "following instructions here: https://opencv.org/?s=releases"
        )
        return

    entities = []
    if CONF_CLASSIFIER not in config:
        dest_path = hass.config.path(DEFAULT_CLASSIFIER_PATH)
        _get_default_classifier(dest_path)
        config[CONF_CLASSIFIER] = {"Face": dest_path}

    for camera in config[CONF_SOURCE]:
        entities.append(
            OpenCVImageProcessor(
                hass,
                camera[CONF_ENTITY_ID],
                camera.get(CONF_NAME),
                config[CONF_CLASSIFIER],
            )
        )

    add_entities(entities)


class OpenCVImageProcessor(ImageProcessingEntity):
    """Representation of an OpenCV image processor."""

    def __init__(self, hass, camera_entity, name, classifiers):
        """Initialize the OpenCV entity."""
        self.hass = hass
        self._camera_entity = camera_entity
        if name:
            self._name = name
        else:
            self._name = f"OpenCV {split_entity_id(camera_entity)[1]}"
        self._classifiers = classifiers
        self._matches = {}
        self._total_matches = 0
        self._last_image = None

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
        return {ATTR_MATCHES: self._matches, ATTR_TOTAL_MATCHES: self._total_matches}

    def process_image(self, image):
        """Process the image."""
        cv_image = cv2.imdecode(np.asarray(bytearray(image)), cv2.IMREAD_UNCHANGED)

        matches = {}
        total_matches = 0

        for name, classifier in self._classifiers.items():
            scale = DEFAULT_SCALE
            neighbors = DEFAULT_NEIGHBORS
            min_size = DEFAULT_MIN_SIZE
            if isinstance(classifier, dict):
                path = classifier[CONF_FILE]
                scale = classifier.get(CONF_SCALE, scale)
                neighbors = classifier.get(CONF_NEIGHBORS, neighbors)
                min_size = classifier.get(CONF_MIN_SIZE, min_size)
            else:
                path = classifier

            cascade = cv2.CascadeClassifier(path)

            detections = cascade.detectMultiScale(
                cv_image, scaleFactor=scale, minNeighbors=neighbors, minSize=min_size
            )
            regions = []
            # pylint: disable=invalid-name
            for x, y, w, h in detections:
                regions.append((int(x), int(y), int(w), int(h)))
                total_matches += 1

            matches[name] = regions

        self._matches = matches
        self._total_matches = total_matches

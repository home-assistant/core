"""
Support for OpenCV image/video processing.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/opencv/
"""
import asyncio
import logging
import os
import voluptuous as vol

from homeassistant.helpers import (
    discovery,
    config_validation as cv
)

from homeassistant.const import (
    CONF_NAME,
    CONF_ENTITY_ID,
    CONF_FILE_PATH,
)

REQUIREMENTS = ['opencv-python==3.2.0.6', 'numpy==1.12.0']

_LOGGER = logging.getLogger(__name__)

ATTR_MATCH_NAME = 'name'
ATTR_MATCH_ID = 'id'
ATTR_MATCH_COORDS = 'coords'
ATTR_MATCH_REGIONS = 'regions'
ATTR_MATCHES = 'matches'

BASE_PATH = os.path.realpath(__file__)

CONF_CLASSIFIER = 'classifier'

DATA_CLASSIFIER_GROUPS = 'classifier_groups'

DEFAULT_CLASSIFIER_PATH = \
    os.path.join(os.path.dirname(BASE_PATH), 'opencv_classifiers', 'haarcascade_frontalface_default.xml')
DEFAULT_CLASSIFIER = [{
    CONF_FILE_PATH: DEFAULT_CLASSIFIER_PATH,
    CONF_NAME: 'Face'
}]
DEFAULT_NAME = 'OpenCV'

DOMAIN = 'opencv'

CLASSIFIER_GROUP_CONFIG = {
    vol.Optional(CONF_CLASSIFIER, default=DEFAULT_CLASSIFIER): vol.All(
        cv.ensure_list,
        [vol.Schema({
            vol.Required(CONF_FILE_PATH): cv.isfile,
            vol.Required(CONF_NAME): cv.string
        })]),
    vol.Required(CONF_ENTITY_ID): cv.entity_ids,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
}
CLASSIFIER_GROUP_SCHEMA = vol.Schema(CLASSIFIER_GROUP_CONFIG)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(
        cv.ensure_list,
        [CLASSIFIER_GROUP_SCHEMA]
    )
}, extra=vol.ALLOW_EXTRA)


@asyncio.coroutine
def draw_regions(cv_image, regions):
    """Draw the regions"""
    import cv2

    for (x, y, w, h) in regions:
        cv2.rectangle(cv_image,
                      (x, y),
                      (x + w, y + h),
                      (255, 255, 0),  # COLOR
                      2)

    return cv_image


@asyncio.coroutine
def _process_classifier(cv2, cv_image, classifier_path, classifier_name):
    """Process the given classifier."""
    classifier = cv2.CascadeClassifier(classifier_path)

    detections = classifier.detectMultiScale(cv_image,
                                             scaleFactor=1.1,
                                             minNeighbors=4,
                                             minSize=(30, 30))
    matches = []
    for (x, y, w, h) in detections:
        matches.append({
            ATTR_MATCH_ID: len(matches),
            ATTR_MATCH_COORDS: {
                'x': int(x),
                'y': int(y),
                'w': int(w),
                'h': int(h),
            }
        })

    if len(detections) > 0:
        return {
            ATTR_MATCH_NAME: classifier_name,
            ATTR_MATCH_REGIONS: matches
        }

    return None


def cv_image_from_bytes(image):
    """Convert image bytes to OpenCV image."""
    import cv2
    import numpy

    return cv2.imdecode(numpy.asarray(bytearray(image)), cv2.IMREAD_UNCHANGED)


@asyncio.coroutine
def process_image(image, classifier_configs):
    import cv2

    cv_image = cv2.imdecode(numpy.asarray(bytearray(image)), cv2.IMREAD_UNCHANGED)
    matches = []
    for classifier_config in classifier_configs:
        match = yield from _process_classifier(cv2,
                                               cv_image,
                                               classifier_config[CONF_FILE_PATH],
                                               classifier_config[CONF_NAME])
        if match is not None:
            matches.append(match)

    return matches


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the OpenCV platform entities."""
    _LOGGER.info('Setting up OpenCV')

    hass.data[DOMAIN] = OpenCV(hass, config[DOMAIN])

    @asyncio.coroutine
    def async_platform_discovered(platform, info):
        """Platform discovered listener."""
        # discovery.load_platform(hass, 'camera', DOMAIN, {}, config)
        _LOGGER.info('async_platform_discovered : %s : %s', str(platform), str(info))

    discovery.async_listen_platform(hass, 'image_processing', async_platform_discovered)
    discovery.load_platform(hass, 'image_processing', DOMAIN, {}, config)

    return True


class OpenCV(object):
    """OpenCV Platform."""
    def __init__(self, hass, classifier_groups):
        """Initialize the OpenCV platform"""
        self._classifier_groups = classifier_groups
        self._image_processors = []

    @property
    def classifier_groups(self):
        """Return configured classifier groups."""
        return self._classifier_groups

    @property
    def image_processors(self):
        """Return the image processor components."""
        return self._image_processors

    def add_image_processor(self, image_processor):
        """Add an image processor to the data store."""
        self._image_processors.append(image_processor)

"""
Support for OpenCV image/video processing.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/opencv/
"""
import asyncio
import logging
import os
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME,
    CONF_ENTITY_ID,
    CONF_FILE_PATH
)
from homeassistant.helpers import (
    discovery,
    config_validation as cv,
)

REQUIREMENTS = ['opencv-python==3.2.0.6', 'numpy==1.12.0', 'urllib3==1.21']

_LOGGER = logging.getLogger(__name__)

ATTR_MATCHES = 'matches'

BASE_PATH = os.path.realpath(__file__)

CASCADE_URL = \
    'https://raw.githubusercontent.com/opencv/opencv/master/data/' +\
    'lbpcascades/lbpcascade_frontalface.xml'

CONF_CLASSIFIER = 'classifier'
CONF_COLOR = 'color'
CONF_GROUPS = 'classifier_group'
CONF_MIN_SIZE = 'min_size'
CONF_NEIGHBORS = 'neighbors'
CONF_SCALE = 'scale'

DATA_CLASSIFIER_GROUPS = 'classifier_groups'

DEFAULT_COLOR = (255, 255, 0)
DEFAULT_CLASSIFIER_PATH = os.path.join(
    os.path.dirname(BASE_PATH),
    'lbp_frontalface.xml')
DEFAULT_NAME = 'OpenCV'
DEFAULT_MIN_SIZE = (30, 30)
DEFAULT_NEIGHBORS = 4
DEFAULT_SCALE = 1.1

DOMAIN = 'opencv'

CLASSIFIER_GROUP_CONFIG = {
    vol.Required(CONF_CLASSIFIER): vol.All(
        cv.ensure_list,
        [vol.Schema({
            vol.Optional(CONF_COLOR, default=DEFAULT_COLOR):
                vol.Schema((int, int, int)),
            vol.Optional(CONF_FILE_PATH, default=DEFAULT_CLASSIFIER_PATH):
                cv.isfile,
            vol.Optional(CONF_NAME, default=DEFAULT_NAME):
                cv.string,
            vol.Optional(CONF_MIN_SIZE, default=DEFAULT_MIN_SIZE):
                vol.Schema((int, int)),
            vol.Optional(CONF_NEIGHBORS, default=DEFAULT_NEIGHBORS):
                cv.positive_int,
            vol.Optional(CONF_SCALE, default=DEFAULT_SCALE):
                float
        })]),
    vol.Required(CONF_ENTITY_ID): cv.entity_ids,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
}
CLASSIFIER_GROUP_SCHEMA = vol.Schema(CLASSIFIER_GROUP_CONFIG)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_GROUPS): vol.All(
            cv.ensure_list,
            [CLASSIFIER_GROUP_SCHEMA]
        ),
    })
}, extra=vol.ALLOW_EXTRA)


# NOTE:
# pylint cannot find any of the members of cv2, using disable=no-member
# to pass linting


def cv_image_to_bytes(cv_image):
    """Convert OpenCV image to bytes."""
    import cv2

    # pylint: disable=no-member
    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
    # pylint: disable=no-member
    success, data = cv2.imencode('.jpg', cv_image, encode_param)

    if success:
        return data.tobytes()

    return None


def cv_image_from_bytes(image):
    """Convert image bytes to OpenCV image."""
    import cv2
    import numpy

    # pylint: disable=no-member
    return cv2.imdecode(numpy.asarray(bytearray(image)), cv2.IMREAD_UNCHANGED)


def process_image(image, classifier_group, is_camera):
    """Process the image given a classifier group."""
    import cv2
    import numpy

    # pylint: disable=no-member
    cv_image = cv2.imdecode(numpy.asarray(bytearray(image)),
                            cv2.IMREAD_UNCHANGED)
    group_matches = {}
    for classifier_config in classifier_group:
        classifier_path = classifier_config[CONF_FILE_PATH]
        classifier_name = classifier_config[CONF_NAME]
        color = classifier_config[CONF_COLOR]
        scale = classifier_config[CONF_SCALE]
        neighbors = classifier_config[CONF_NEIGHBORS]
        min_size = classifier_config[CONF_MIN_SIZE]

        # pylint: disable=no-member
        classifier = cv2.CascadeClassifier(classifier_path)

        detections = classifier.detectMultiScale(cv_image,
                                                 scaleFactor=scale,
                                                 minNeighbors=neighbors,
                                                 minSize=min_size)
        regions = []
        # pylint: disable=invalid-name
        for (x, y, w, h) in detections:
            if is_camera:
                # pylint: disable=no-member
                cv2.rectangle(cv_image,
                              (x, y),
                              (x + w, y + h),
                              color,
                              2)
            else:
                regions.append((int(x), int(y), int(w), int(h)))
        group_matches[classifier_name] = regions

    if is_camera:
        return cv_image_to_bytes(cv_image)
    else:
        return group_matches


@asyncio.coroutine
def async_setup(hass, config):
    """Set up the OpenCV platform entities."""
    _LOGGER.info('Async setup for opencv')
    if not os.path.isfile(DEFAULT_CLASSIFIER_PATH):
        _LOGGER.info('Downloading default classifier')
        import urllib3

        http = urllib3.PoolManager()
        request = http.request('GET', CASCADE_URL, preload_content=False)

        with open(DEFAULT_CLASSIFIER_PATH, 'wb') as out:
            while True:
                data = request.read(1028)
                if not data:
                    break
                out.write(data)

        request.release_conn()

    for group in config[DOMAIN][CONF_GROUPS]:
        discovery.load_platform(hass, 'image_processing', DOMAIN, group)

    return True

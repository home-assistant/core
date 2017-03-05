"""
Component that performs OpenCV processes on images

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/image_processing.opencv/
"""
import asyncio
import logging
import os
import voluptuous as vol

from homeassistant.components.image_processing import (
    ImageProcessingEntity,
    PLATFORM_SCHEMA,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_ENTITY_ID,
    CONF_FILE_PATH,
)
from homeassistant.core import split_entity_id
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['opencv-python==3.2.0.6', 'numpy==1.12.0']

_LOGGER = logging.getLogger(__name__)

ATTR_MATCH_NAME = 'name'
ATTR_MATCH_ID = 'id'
ATTR_MATCH_COORDS = 'coords'
ATTR_MATCH_REGIONS = 'regions'
ATTR_MATCHES = 'matches'

BASE_PATH = os.path.realpath(__file__)

CONF_CLASSIFIER = 'classifier'

DEFAULT_NAME = 'OpenCV'
DEFAULT_CLASSIFIER_PATH = \
    os.path.join(os.path.dirname(BASE_PATH), 'opencv_classifiers', 'haarcascade_frontalface_default.xml')
DEFAULT_TIMEOUT = 10
DEFAULT_CLASSIFIER = [{
    CONF_FILE_PATH: DEFAULT_CLASSIFIER_PATH,
    CONF_NAME: 'Face'
}]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_CLASSIFIER, default=DEFAULT_CLASSIFIER): vol.All(
        cv.ensure_list,
        [vol.Schema({
            vol.Required(CONF_FILE_PATH): cv.isfile,
            vol.Required(CONF_NAME): cv.string
        })]),
    vol.Required(CONF_ENTITY_ID): cv.entity_ids,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the OpenCV image processing platform."""
    devices = []
    if config is None:
        config = discovery_info

    for camera_entity in config[CONF_ENTITY_ID]:
        classifier_config = config[CONF_CLASSIFIER]
        name = '{} {}'.format(
            config[CONF_NAME],
            split_entity_id(camera_entity)[1])

        _LOGGER.info('Found %s for %s', name, camera_entity)

        devices.append(OpenCVImageProcessor(
            camera_entity,
            name,
            classifier_config,
        ))

    _LOGGER.info('Found %i devices', len(devices))
    async_add_devices(devices)

class OpenCVImageProcessor(ImageProcessingEntity):
    """Representation of an OpenCV image processor."""

    def __init__(self, camera_entity, name, classifier_configs):
        """Initialize the OpenCV entity."""
        self._camera_entity = camera_entity
        self._name = name
        self._cv_image = None
        self._classifier_configs = classifier_configs
        self._matches = []

    @property
    def processed_image(self):
        return self._cv_image

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
        return len(self._matches)

    @asyncio.coroutine
    def _process_classifier(self, cv2, cv_image, classifer_config):
        """Process the given classifier."""
        classifier_path = classifer_config[CONF_FILE_PATH]
        classifier_name = classifer_config[CONF_NAME]
        classifier = cv2.CascadeClassifier(classifier_path)

        detections = classifier.detectMultiScale(cv_image,
                                                 scaleFactor=1.1,
                                                 minNeighbors=4,
                                                 minSize=(30, 30))
        matches = []
        for (x, y, w, h) in detections:
            cv2.rectangle(cv_image,
                          (x, y),
                          (x + w, y + h),
                          (255, 255, 0),
                          2)
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

    @asyncio.coroutine
    def async_process_image(self, image):
        """Process the image asynchronously."""
        import cv2
        import numpy

        _LOGGER.info('Processing image size %i', len(str(image)))

        cv_image = cv2.imdecode(numpy.asarray(bytearray(image)), cv2.IMREAD_UNCHANGED)
        _LOGGER.info('CV Image %i', len(str(cv_image)))
        matches = []
        for classifier_confg in self._classifier_configs:
            match = yield from self._process_classifier(cv2, cv_image, classifier_confg)
            if match is not None:
                matches.append(match)

        self._matches = matches  # TODO : Check for diffs

        # TODO : Fire Event

        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 90]
        success, data = cv2.imencode('.jpg', cv_image, encode_param)

        if success:
            self._cv_image = data.tobytes()

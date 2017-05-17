"""
Component that performs OpenCV classification on images.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/image_processing.opencv/
"""
from datetime import timedelta
import logging

from homeassistant.core import split_entity_id
from homeassistant.components.image_processing import (
    ImageProcessingEntity, PLATFORM_SCHEMA)
from homeassistant.components.opencv import (
    ATTR_MATCHES, CLASSIFIER_GROUP_CONFIG, CONF_CLASSIFIER, CONF_ENTITY_ID,
    CONF_NAME, process_image)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['opencv']

DEFAULT_TIMEOUT = 10

SCAN_INTERVAL = timedelta(seconds=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(CLASSIFIER_GROUP_CONFIG)


def _create_processor_from_config(hass, camera_entity, config):
    """Create an OpenCV processor from configuration."""
    classifier_config = config[CONF_CLASSIFIER]
    name = '{} {}'.format(
        config[CONF_NAME], split_entity_id(camera_entity)[1].replace('_', ' '))

    processor = OpenCVImageProcessor(
        hass, camera_entity, name, classifier_config)

    return processor


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the OpenCV image processing platform."""
    if discovery_info is None:
        return

    devices = []
    for camera_entity in discovery_info[CONF_ENTITY_ID]:
        devices.append(
            _create_processor_from_config(hass, camera_entity, discovery_info))

    add_devices(devices)


class OpenCVImageProcessor(ImageProcessingEntity):
    """Representation of an OpenCV image processor."""

    def __init__(self, hass, camera_entity, name, classifier_configs):
        """Initialize the OpenCV entity."""
        self.hass = hass
        self._camera_entity = camera_entity
        self._name = name
        self._classifier_configs = classifier_configs
        self._matches = {}
        self._last_image = None

    @property
    def last_image(self):
        """Return the last image."""
        return self._last_image

    @property
    def matches(self):
        """Return the matches it found."""
        return self._matches

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
        total_matches = 0
        for group in self._matches.values():
            total_matches += len(group)
        return total_matches

    @property
    def state_attributes(self):
        """Return device specific state attributes."""
        return {
            ATTR_MATCHES: self._matches
        }

    def process_image(self, image):
        """Process the image."""
        self._last_image = image
        self._matches = process_image(
            image, self._classifier_configs, False)

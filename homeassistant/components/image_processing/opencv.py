"""
Component that performs OpenCV processes on images.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/image_processing.opencv/
"""
import asyncio
import logging

from homeassistant.components.opencv import (
    ATTR_MATCHES,
    CLASSIFIER_GROUP_CONFIG,
    CONF_CLASSIFIER,
    CONF_ENTITY_ID,
    CONF_NAME,
    DOMAIN as OPENCV_DOMAIN,
    process_image,
)
from homeassistant.components.image_processing import (
    ImageProcessingEntity,
    PLATFORM_SCHEMA,
)
from homeassistant.core import split_entity_id

DEPENDENCIES = ['opencv']

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(CLASSIFIER_GROUP_CONFIG)

EVENT_FOUND_MATCH = 'image_processing.opencv_found_{}'


def _create_processor_from_config(hass, camera_entity, config):
    """Create an OpenCV processor from configurtaion."""
    classifier_config = config[CONF_CLASSIFIER]
    name = '{} {}'.format(
        config[CONF_NAME],
        split_entity_id(camera_entity)[1])

    processor = OpenCVImageProcessor(
        hass,
        camera_entity,
        name,
        classifier_config,
    )
    hass.data[OPENCV_DOMAIN].add_image_processor(processor)

    return processor


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the OpenCV image processing platform."""
    devices = []
    if discovery_info is not None:
        # Create image processor from discovery info
        for classifier_group in hass.data[OPENCV_DOMAIN].classifier_groups:
            for camera_entity in classifier_group[CONF_ENTITY_ID]:
                devices.append(
                    _create_processor_from_config(
                        hass,
                        camera_entity,
                        classifier_group))
    else:
        # Allow for creation of image processor directly
        for camera_entity in config[CONF_ENTITY_ID]:
            devices.append(
                _create_processor_from_config(
                    hass,
                    camera_entity,
                    config))

    async_add_devices(devices)


class OpenCVImageProcessor(ImageProcessingEntity):
    """Representation of an OpenCV image processor."""

    def __init__(self, hass, camera_entity, name, classifier_configs):
        """Initialize the OpenCV entity."""
        self.hass = hass
        self._camera_entity = camera_entity
        self._name = name
        self._classifier_configs = classifier_configs
        self._matches = []

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
        return len(self._matches)

    @property
    def state_attributes(self):
        """Return device specific state attributes."""
        return {
            ATTR_MATCHES: str(self._matches)
        }

    @asyncio.coroutine
    def async_process_image(self, image):
        """Process the image asynchronously."""
        self._matches = yield from process_image(image,
                                                 self._classifier_configs)

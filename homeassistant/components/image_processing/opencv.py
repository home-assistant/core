"""
Component that performs OpenCV processes on images

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/image_processing.opencv/
"""
import asyncio
import logging
import os
import voluptuous as vol

from homeassistant.components.opencv import (
    ATTR_MATCHES,
    ATTR_MATCH_COORDS,
    ATTR_MATCH_ID,
    ATTR_MATCH_NAME,
    ATTR_MATCH_REGIONS,
    CLASSIFIER_GROUP_CONFIG,
    CONF_CLASSIFIER,
    CONF_ENTITY_ID,
    CONF_FILE_PATH,
    CONF_NAME,
    process_image,
)
from homeassistant.components.image_processing import (
    ImageProcessingEntity,
    PLATFORM_SCHEMA,
)
from homeassistant.core import split_entity_id


_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(CLASSIFIER_GROUP_CONFIG)


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

        devices.append(OpenCVImageProcessor(
            camera_entity,
            name,
            classifier_config,
        ))

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

    @property
    def state_attributes(self):
        """Return device specific state attributes."""
        return {
            ATTR_MATCHES: str(self._matches)
        }

    @asyncio.coroutine
    def async_process_image(self, image):
        """Process the image asynchronously."""
        process_image(image, self._classifier_configs)

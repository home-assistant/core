"""
Component that will help set the openalpr cloud for alpr processing.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/image_processing.openalpr_cloud/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.const import CONF_API_KEY
import homeassistant.helpers.config_validation as cv
from homeassistant.components.image_processing import (
    PLATFORM_SCHEMA, ImageProcessingAlprEntity, CONF_CONFIDENCE, CONF_SOURCE,
    CONF_ENTITY_ID, CONF_NAME)

_LOGGER = logging.getLogger(__name__)

OPENALPR_REGIONS = [
    'us',
    'eu',
    'au',
    'auwide',
    'gb',
    'kr',
    'mx',
    'sg',
]

CONF_REGION = 'region'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Required(CONF_REGION):
        vol.All(vol.Lower, vol.In(OPENALPR_REGIONS)),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the openalpr cloud api platform."""


class OpenAlprCloudEntity(ImageProcessingAlprEntity):
    """OpenAlpr cloud entity."""

    def async_process_image(self, image):
        """Process image.

        This method is a coroutine.
        """

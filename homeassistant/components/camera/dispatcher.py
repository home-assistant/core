"""
Support for internal dispatcher image push to Camera.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.dispatcher/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.const import CONF_NAME
from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

CONF_SIGNAL = 'signal'
DEFAULT_NAME = 'Dispatcher Camera'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_SIGNAL): cv.slugify,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Setup a dispatcher camera."""
    if discovery_info:
        config = PLATFORM_SCHEMA(discovery_info)

    async_add_devices(
        [DispatcherCamera(config[CONF_NAME], config[CONF_SIGNAL])])


class DispatcherCamera(Camera):
    """A dispatcher implementation of an camera."""

    def __init__(self, name, signal):
        """Initialize a dispatcher camera."""
        super().__init__()
        self._name = name
        self._signal = signal
        self._image = None

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register dispatcher and callbacks."""
        @callback
        def async_update_image(image):
            """Update image from dispatcher call."""
            self._image = image

        async_dispatcher_connect(self.hass, self._signal, async_update_image)

    @asyncio.coroutine
    def async_camera_image(self):
        """Return a still image response from the camera."""
        return self._image

    @property
    def name(self):
        """Return the name of this device."""
        return self._name

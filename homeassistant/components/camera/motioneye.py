"""
Support for motionEye Cameras.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/camera.motioneye/
"""
import logging

import voluptuous as vol

from homeassistant.components.camera import (PLATFORM_SCHEMA, Camera)
from homeassistant.const import (CONF_HOST, CONF_SSL, CONF_USERNAME,
                                 CONF_PASSWORD, CONF_VERIFY_SSL)
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

REQUIREMENTS = ['pymotion==0.1.6']

_LOGGER = logging.getLogger(__name__)

CONF_API_PORT = 'api_port'
CONF_WEB_PORT = 'web_port'

DEFAULT_WEB_PORT = 8765
DEFAULT_API_PORT = 7999

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_API_PORT, default=DEFAULT_API_PORT): cv.port,
    vol.Optional(CONF_WEB_PORT, default=DEFAULT_WEB_PORT): cv.port,
    vol.Optional(CONF_USERNAME): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_SSL, default=False): cv.boolean,
    vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up a generic IP Camera."""
    from pymotion.api import API
    session = async_get_clientsession(hass, config[CONF_VERIFY_SSL])
    motion = API(session, hass.loop, config.get(CONF_USERNAME),
                 config.get(CONF_PASSWORD), config[CONF_HOST],
                 config[CONF_API_PORT], config[CONF_WEB_PORT],
                 config[CONF_SSL])
    all_cameraes = await motion.list_cameraes()
    if all_cameraes is None:
        raise PlatformNotReady
    cameraes = []
    for camera_id in all_cameraes:
        name = all_cameraes[camera_id]['name']
        cameraes.append(MotionEyeCamera(name, motion, camera_id))

    async_add_entities(cameraes)


class MotionEyeCamera(Camera):
    """A generic implementation of an IP camera."""

    def __init__(self, name, motion, camera_id):
        """Initialize a generic camera."""
        super().__init__()
        self.motion = motion
        self._name = name
        self._camera_id = camera_id
        self._last_image = None

    async def async_camera_image(self):
        """Return image response."""
        image = await self.motion.camera_image(self._camera_id)
        if image is not None:
            self._last_image = image
        return self._last_image

    @property
    def name(self):
        """Return the name of this device."""
        return self._name

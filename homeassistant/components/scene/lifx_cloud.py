"""
Support for LIFX Cloud scenes.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/scene.lifx_cloud/
"""
import asyncio
import logging

import aiohttp
from aiohttp.hdrs import AUTHORIZATION
import async_timeout
import voluptuous as vol

from homeassistant.components.scene import Scene
from homeassistant.const import CONF_TOKEN, CONF_TIMEOUT, CONF_PLATFORM
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

LIFX_API_URL = 'https://api.lifx.com/v1/{0}'
DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'lifx_cloud',
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the scenes stored in the LIFX Cloud."""
    token = config.get(CONF_TOKEN)
    timeout = config.get(CONF_TIMEOUT)

    headers = {
        AUTHORIZATION: "Bearer {}".format(token),
    }

    url = LIFX_API_URL.format('scenes')

    try:
        httpsession = async_get_clientsession(hass)
        with async_timeout.timeout(timeout, loop=hass.loop):
            scenes_resp = yield from httpsession.get(url, headers=headers)

    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.exception("Error on %s", url)
        return False

    status = scenes_resp.status
    if status == 200:
        data = yield from scenes_resp.json()
        devices = []
        for scene in data:
            devices.append(LifxCloudScene(hass, headers, timeout, scene))
        async_add_devices(devices)
        return True
    if status == 401:
        _LOGGER.error("Unauthorized (bad token?) on %s", url)
        return False

    _LOGGER.error("HTTP error %d on %s", scenes_resp.status, url)
    return False


class LifxCloudScene(Scene):
    """Representation of a LIFX Cloud scene."""

    def __init__(self, hass, headers, timeout, scene_data):
        """Initialize the scene."""
        self.hass = hass
        self._headers = headers
        self._timeout = timeout
        self._name = scene_data["name"]
        self._uuid = scene_data["uuid"]

    @property
    def name(self):
        """Return the name of the scene."""
        return self._name

    @asyncio.coroutine
    def async_activate(self):
        """Activate the scene."""
        url = LIFX_API_URL.format('scenes/scene_id:%s/activate' % self._uuid)

        try:
            httpsession = async_get_clientsession(self.hass)
            with async_timeout.timeout(self._timeout, loop=self.hass.loop):
                yield from httpsession.put(url, headers=self._headers)

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.exception("Error on %s", url)

"""Support for LIFX Cloud scenes."""
import asyncio
import logging
from typing import Any

import aiohttp
from aiohttp.hdrs import AUTHORIZATION
import async_timeout
import voluptuous as vol

from homeassistant.components.scene import Scene
from homeassistant.const import (
    CONF_PLATFORM,
    CONF_TIMEOUT,
    CONF_TOKEN,
    HTTP_OK,
    HTTP_UNAUTHORIZED,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 10

PLATFORM_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PLATFORM): "lifx_cloud",
        vol.Required(CONF_TOKEN): cv.string,
        vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): cv.positive_int,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the scenes stored in the LIFX Cloud."""
    token = config.get(CONF_TOKEN)
    timeout = config.get(CONF_TIMEOUT)

    headers = {AUTHORIZATION: f"Bearer {token}"}

    url = "https://api.lifx.com/v1/scenes"

    try:
        httpsession = async_get_clientsession(hass)
        with async_timeout.timeout(timeout):
            scenes_resp = await httpsession.get(url, headers=headers)

    except (asyncio.TimeoutError, aiohttp.ClientError):
        _LOGGER.exception("Error on %s", url)
        return False

    status = scenes_resp.status
    if status == HTTP_OK:
        data = await scenes_resp.json()
        devices = [LifxCloudScene(hass, headers, timeout, scene) for scene in data]
        async_add_entities(devices)
        return True
    if status == HTTP_UNAUTHORIZED:
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

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scene."""
        url = f"https://api.lifx.com/v1/scenes/scene_id:{self._uuid}/activate"

        try:
            httpsession = async_get_clientsession(self.hass)
            with async_timeout.timeout(self._timeout):
                await httpsession.put(url, headers=self._headers)

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.exception("Error on %s", url)

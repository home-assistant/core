"""Support for a Genius Hub system."""
from datetime import timedelta
import logging

import voluptuous as vol

from geniushubclient import GeniusHubClient

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

_LOGGER = logging.getLogger(__name__)

DOMAIN = "geniushub"

SCAN_INTERVAL = timedelta(seconds=60)

_V1_API_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): cv.string})
_V3_API_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)
CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Any(_V3_API_SCHEMA, _V1_API_SCHEMA)}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass, hass_config):
    """Create a Genius Hub system."""
    kwargs = dict(hass_config[DOMAIN])
    if CONF_HOST in kwargs:
        args = (kwargs.pop(CONF_HOST),)
    else:
        args = (kwargs.pop(CONF_TOKEN),)

    hass.data[DOMAIN] = {}
    data = hass.data[DOMAIN]["data"] = GeniusData(hass, args, kwargs)
    try:
        await data._client.hub.update()  # pylint: disable=protected-access
    except AssertionError:  # assert response.status == HTTP_OK
        _LOGGER.warning("Setup failed, check your configuration.", exc_info=True)
        return False

    _LOGGER.debug(
        # noqa; pylint: disable=protected-access
        "zones_raw = %s",
        data._client.hub._zones_raw,
    )
    _LOGGER.debug(
        # noqa; pylint: disable=protected-access
        "devices_raw = %s",
        data._client.hub._devices_raw,
    )

    async_track_time_interval(hass, data.async_update, SCAN_INTERVAL)

    for platform in ["climate", "water_heater"]:
        hass.async_create_task(
            async_load_platform(hass, platform, DOMAIN, {}, hass_config)
        )

    if data._client.api_version == 3:  # pylint: disable=protected-access
        for platform in ["sensor", "binary_sensor"]:
            hass.async_create_task(
                async_load_platform(hass, platform, DOMAIN, {}, hass_config)
            )

    return True


class GeniusData:
    """Container for geniushub client and data."""

    def __init__(self, hass, args, kwargs):
        """Initialize the geniushub client."""
        self._hass = hass
        self._client = hass.data[DOMAIN]["client"] = GeniusHubClient(
            *args, **kwargs, session=async_get_clientsession(hass)
        )

    async def async_update(self, now, **kwargs):
        """Update the geniushub client's data."""
        try:
            await self._client.hub.update()
        except AssertionError:  # assert response.status == HTTP_OK
            _LOGGER.warning("Update failed.", exc_info=True)
            return

        _LOGGER.debug(
            # noqa; pylint: disable=protected-access
            "zones_raw = %s",
            self._client.hub._zones_raw,
        )
        _LOGGER.debug(
            # noqa; pylint: disable=protected-access
            "devices_raw = %s",
            self._client.hub._devices_raw,
        )

        async_dispatcher_send(self._hass, DOMAIN)

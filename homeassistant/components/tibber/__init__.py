"""Support for Tibber."""
import asyncio
import logging

import aiohttp
import tibber
import voluptuous as vol

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

DOMAIN = "tibber"

DEFAULT_RETRY = 120


CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema({vol.Required(CONF_ACCESS_TOKEN): cv.string})},
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the Tibber component."""
    conf = config.get(DOMAIN)

    tibber_connection = tibber.Tibber(
        conf[CONF_ACCESS_TOKEN],
        websession=async_get_clientsession(hass),
        time_zone=dt_util.DEFAULT_TIME_ZONE,
    )
    hass.data[DOMAIN] = tibber_connection

    async def _close(event):
        await tibber_connection.rt_disconnect()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close)

    try:
        await tibber_connection.update_info()
    except asyncio.TimeoutError:
        _LOGGER.warning(
            "Timeout connecting to Tibber. Will retry in %ss", DEFAULT_RETRY
        )

        async def retry_setup(now):
            """Retry setup if a connection/timeout happens on Slide API."""
            await async_setup(hass, config)

        async_call_later(hass, DEFAULT_RETRY, retry_setup)

        return True
    except aiohttp.ClientError as err:
        _LOGGER.error("Error connecting to Tibber: %s ", err)
        return False
    except tibber.InvalidLogin as exp:
        _LOGGER.error("Failed to login. %s", exp)
        return False

    for component in ["sensor", "notify"]:
        discovery.load_platform(hass, component, DOMAIN, {CONF_NAME: DOMAIN}, config)

    return True

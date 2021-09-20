"""Support for Tibber."""
import asyncio
import logging

import aiohttp
import tibber
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.util import dt as dt_util

from .const import DATA_HASS_CONFIG, DOMAIN

PLATFORMS = [
    "sensor",
]

CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(DOMAIN),
        {DOMAIN: vol.Schema({vol.Required(CONF_ACCESS_TOKEN): cv.string})},
    ),
    extra=vol.ALLOW_EXTRA,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass, config):
    """Set up the Tibber component."""

    hass.data[DATA_HASS_CONFIG] = config

    if DOMAIN not in config:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=config[DOMAIN],
        )
    )

    return True


async def async_setup_entry(hass, entry):
    """Set up a config entry."""

    tibber_connection = tibber.Tibber(
        access_token=entry.data[CONF_ACCESS_TOKEN],
        websession=async_get_clientsession(hass),
        time_zone=dt_util.DEFAULT_TIME_ZONE,
    )
    hass.data[DOMAIN] = tibber_connection

    async def _close(event):
        await tibber_connection.rt_disconnect()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close))

    try:
        await tibber_connection.update_info()
    except asyncio.TimeoutError as err:
        raise ConfigEntryNotReady from err
    except aiohttp.ClientError as err:
        _LOGGER.error("Error connecting to Tibber: %s ", err)
        return False
    except tibber.InvalidLogin as exp:
        _LOGGER.error("Failed to login. %s", exp)
        return False

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    # set up notify platform, no entry support for notify component yet,
    # have to use discovery to load platform.
    hass.async_create_task(
        discovery.async_load_platform(
            hass, "notify", DOMAIN, {CONF_NAME: DOMAIN}, hass.data[DATA_HASS_CONFIG]
        )
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        tibber_connection = hass.data.get(DOMAIN)
        await tibber_connection.rt_disconnect()
    return unload_ok

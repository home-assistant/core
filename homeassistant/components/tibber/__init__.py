"""Support for Tibber."""

import logging

import aiohttp
import tibber

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util, ssl as ssl_util

from .const import DATA_HASS_CONFIG, DOMAIN
from .services import async_setup_services

PLATFORMS = [Platform.NOTIFY, Platform.SENSOR]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tibber component."""

    hass.data[DATA_HASS_CONFIG] = config

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""

    tibber_connection = tibber.Tibber(
        access_token=entry.data[CONF_ACCESS_TOKEN],
        websession=async_get_clientsession(hass),
        time_zone=dt_util.get_default_time_zone(),
        ssl=ssl_util.get_default_context(),
    )
    hass.data[DOMAIN] = tibber_connection

    async def _close(event: Event) -> None:
        await tibber_connection.rt_disconnect()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _close))

    try:
        await tibber_connection.update_info()

    except (
        TimeoutError,
        aiohttp.ClientError,
        tibber.RetryableHttpExceptionError,
    ) as err:
        raise ConfigEntryNotReady("Unable to connect") from err
    except tibber.InvalidLoginError as exp:
        _LOGGER.error("Failed to login. %s", exp)
        return False
    except tibber.FatalHttpExceptionError:
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if unload_ok:
        tibber_connection = hass.data[DOMAIN]
        await tibber_connection.rt_disconnect()
    return unload_ok

"""Support for Tibber."""

import logging

import aiohttp
import tibber

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_NAME,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import discovery
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import DATA_HASS_CONFIG, DOMAIN

PLATFORMS = [Platform.NOTIFY, Platform.SENSOR]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Tibber component."""

    hass.data[DATA_HASS_CONFIG] = config
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""

    tibber_connection = tibber.Tibber(
        access_token=entry.data[CONF_ACCESS_TOKEN],
        websession=async_get_clientsession(hass),
        time_zone=dt_util.DEFAULT_TIME_ZONE,
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
        tibber.RetryableHttpException,
    ) as err:
        raise ConfigEntryNotReady("Unable to connect") from err
    except tibber.InvalidLogin as exp:
        _LOGGER.error("Failed to login. %s", exp)
        return False
    except tibber.FatalHttpException:
        return False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Use discovery to load platform legacy notify platform
    # The use of the legacy notify service was deprecated with HA Core 2024.6
    # Support will be removed with HA Core 2024.12
    hass.async_create_task(
        discovery.async_load_platform(
            hass,
            Platform.NOTIFY,
            DOMAIN,
            {CONF_NAME: DOMAIN},
            hass.data[DATA_HASS_CONFIG],
        )
    )

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

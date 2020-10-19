"""The Omnilogic integration."""
import asyncio
import logging

from omnilogic import LoginException, OmniLogic, OmniLogicException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client

from .common import OmniLogicUpdateCoordinator
from .const import (
    CONF_SCAN_INTERVAL,
    COORDINATOR,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    OMNI_API,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "water_heater", "light", "switch"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Omnilogic from a config entry."""

    conf = entry.data
    username = conf[CONF_USERNAME]
    password = conf[CONF_PASSWORD]

    polling_interval = conf.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    session = aiohttp_client.async_get_clientsession(hass)

    api = OmniLogic(username, password, session)

    try:
        await api.connect()
        await api.get_telemetry_data()
    except LoginException as error:
        _LOGGER.error("Login Failed: %s", error)
        return False
    except OmniLogicException as error:
        _LOGGER.debug("OmniLogic API error: %s", error)
        raise ConfigEntryNotReady from error

    coordinator = OmniLogicUpdateCoordinator(
        hass=hass,
        api=api,
        name="Omnilogic",
        config_entry=entry,
        polling_interval=polling_interval,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        COORDINATOR: coordinator,
        OMNI_API: api,
    }

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

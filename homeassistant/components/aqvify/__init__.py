"""The Aqvify integration."""

import logging

from pyaqvify import AqvifyAPI, AqvifyAuthException

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import AqvifyConfigEntry, AqvifyCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AqvifyConfigEntry) -> bool:
    """Set up Aqvify from a config entry."""

    _api = AqvifyAPI(entry.data[CONF_API_KEY], websession=async_get_clientsession(hass))
    try:
        await _api.async_get_account_id()
    except AqvifyAuthException as err:
        raise ConfigEntryAuthFailed(f"Invalid Aqvify API key: {err}") from err
    except Exception as err:
        raise ConfigEntryNotReady(f"Failed to connect to Aqvify API: {err}") from err

    coordinator = AqvifyCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AqvifyConfigEntry) -> bool:
    """Unload Aqvify config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

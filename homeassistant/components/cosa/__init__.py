"""The Cosa integration."""

from __future__ import annotations

import logging

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import CosaApi, CosaAuthError, CosaConnectionError
from .coordinator import CosaCoordinator
from .types import CosaConfigEntry, CosaData

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: CosaConfigEntry) -> bool:
    """Set up Cosa from a config entry."""
    session = async_get_clientsession(hass)
    api = CosaApi(entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD], session)

    try:
        await api.async_check_connection()
    except CosaAuthError as err:
        raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
    except CosaConnectionError as err:
        raise ConfigEntryNotReady(f"Unable to connect to Cosa API: {err}") from err

    endpoints = await api.async_get_endpoints()
    if not endpoints:
        raise ConfigEntryNotReady("No thermostat endpoints found")

    coordinators: dict[str, CosaCoordinator] = {}
    for endpoint in endpoints:
        endpoint_id = endpoint["id"]
        coordinator = CosaCoordinator(hass, entry, api, endpoint_id)
        await coordinator.async_config_entry_first_refresh()
        coordinators[endpoint_id] = coordinator

    entry.runtime_data = CosaData(coordinators=coordinators)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: CosaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

"""The Compit integration."""

from __future__ import annotations

import logging

from compit_inext_api import (
    CannotConnect,
    CompitAPI,
    DeviceDefinitionsLoader,
    InvalidAuth,
    SystemInfo,
)

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import CompitConfigEntry, CompitDataUpdateCoordinator

PLATFORMS = [
    Platform.CLIMATE,
]

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, entry: CompitConfigEntry) -> bool:
    """Set up Compit from a config entry."""

    session = async_get_clientsession(hass)
    api = CompitAPI(entry.data["email"], entry.data["password"], session)
    try:
        system_info = await api.authenticate()
    except CannotConnect as e:
        raise ConfigEntryNotReady(f"Error while connecting to Compit: {e}") from e
    except InvalidAuth as e:
        raise ConfigEntryAuthFailed(
            f"Invalid credentials for {entry.data['email']}"
        ) from e

    if isinstance(system_info, SystemInfo):
        try:
            device_definitions = await DeviceDefinitionsLoader.get_device_definitions(
                hass.config.language
            )
        except ValueError as e:
            raise ConfigEntryError("Invalid data returned from api") from e

        coordinator = CompitDataUpdateCoordinator(
            hass, system_info.gates, api, device_definitions
        )
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        return True

    raise ConfigEntryAuthFailed("Authentication API error")


async def async_unload_entry(hass: HomeAssistant, entry: CompitConfigEntry) -> bool:
    """Unload an entry for the Compit integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

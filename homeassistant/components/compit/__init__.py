"""The Compit integration."""

from __future__ import annotations

import logging

from compit_inext_api import (
    CannotConnect,
    CompitAPI,
    DeviceDefinitionsLoader,
    InvalidAuth,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import PLATFORMS
from .coordinator import CompitDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry[CompitDataUpdateCoordinator]
) -> bool:
    """Set up Compit from a config entry."""

    session = async_get_clientsession(hass)
    api = CompitAPI(entry.data["email"], entry.data["password"], session)
    try:
        system_info = await api.authenticate()

        if system_info is False:
            _LOGGER.warning("Compit api error")
            return False

        device_definitions = await DeviceDefinitionsLoader.get_device_definitions(
            hass.config.language
        )

        coordinator = CompitDataUpdateCoordinator(
            hass, system_info.gates, api, device_definitions
        )
        await coordinator.async_config_entry_first_refresh()
        entry.runtime_data = coordinator
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except CannotConnect as e:
        _LOGGER.warning("Cannot connect: %s", e)
        return False
    except InvalidAuth as e:
        raise ConfigEntryAuthFailed(
            f"Invalid credentials for {entry.data["email"]}"
        ) from e
    except ValueError as e:
        _LOGGER.warning("Value error: %s", e)
        return False
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry[CompitDataUpdateCoordinator]
) -> bool:
    """Unload an entry for the Compit integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

"""The Compit integration."""

from __future__ import annotations

import logging

from compit_inext_api import CompitAPI, DeviceDefinitionsLoader

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN, PLATFORMS
from .coordinator import CompitDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Compit from a config entry."""

    session = async_get_clientsession(hass)
    api = CompitAPI(entry.data["email"], entry.data["password"], session)
    try:
        system_info = await api.authenticate()

        if system_info is False:
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

    except ValueError as e:
        _LOGGER.error("Value error: %s", e)
        return False
    except Exception as e:  # noqa: BLE001
        _LOGGER.error("Unexpected exception: %s", e)
        return False
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an entry for the Compit integration."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

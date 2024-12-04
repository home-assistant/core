"""The Axion Lighting integration."""

from __future__ import annotations

from dataclasses import dataclass

from libaxion_dmx import AxionDmxApi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_CHANNEL, CONF_HOST, CONF_PASSWORD
from .coordinator import AxionDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]


@dataclass
class AxionData:
    """Represent a config for Axion Light."""

    coordinator: AxionDataUpdateCoordinator
    api: AxionDmxApi


type AxionConfigEntry = ConfigEntry[AxionData]


async def async_setup_entry(hass: HomeAssistant, entry: AxionConfigEntry) -> bool:
    """Set up Axion Lighting from a config entry."""

    # Create API instance
    api = AxionDmxApi(entry.data[CONF_HOST], entry.data[CONF_PASSWORD])

    # Validate the API connection (and authentication)
    if not await api.authenticate():
        return False

    # Create coordinator instance
    coordinator = AxionDataUpdateCoordinator(hass, api, entry.data[CONF_CHANNEL])
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator and API objects in runtime_data
    entry.runtime_data = AxionData(coordinator=coordinator, api=api)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AxionConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

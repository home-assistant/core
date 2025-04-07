"""The Sensoterra integration."""

from __future__ import annotations

from sensoterra.customerapi import CustomerApi

from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant

from .coordinator import SensoterraConfigEntry, SensoterraCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SensoterraConfigEntry) -> bool:
    """Set up Sensoterra platform based on a configuration entry."""

    # Create a coordinator and add an API instance to it. Store the coordinator
    # in the configuration entry.
    api = CustomerApi()
    api.set_language(hass.config.language)
    api.set_token(entry.data[CONF_TOKEN])

    coordinator = SensoterraCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SensoterraConfigEntry) -> bool:
    """Unload the configuration entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

"""The Garages Amsterdam integration."""

from __future__ import annotations

from odp_amsterdam import ODPAmsterdam

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import GaragesAmsterdamDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

type GaragesAmsterdamConfigEntry = ConfigEntry[GaragesAmsterdamDataUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: GaragesAmsterdamConfigEntry
) -> bool:
    """Set up Garages Amsterdam from a config entry."""
    client = ODPAmsterdam(session=async_get_clientsession(hass))
    coordinator = GaragesAmsterdamDataUpdateCoordinator(hass, client)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GaragesAmsterdamConfigEntry
) -> bool:
    """Unload Garages Amsterdam config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

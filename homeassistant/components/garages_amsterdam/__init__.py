"""The Garages Amsterdam integration."""

from __future__ import annotations

from odp_amsterdam import ODPAmsterdam

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import GaragesAmsterdamDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

type GaragesAmsterdamConfigEntry = ConfigEntry[GaragesAmsterdamDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Garages Amsterdam from a config entry."""
    client = ODPAmsterdam(session=async_get_clientsession(hass))
    coordinator = GaragesAmsterdamDataUpdateCoordinator(hass, client)

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Garages Amsterdam config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if len(hass.config_entries.async_entries(DOMAIN)) == 1:
        hass.data.pop(DOMAIN)

    return unload_ok

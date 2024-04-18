"""Integration for Tailwind devices."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import TailwindDataUpdateCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.BUTTON, Platform.COVER, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Tailwind device from a config entry."""
    coordinator = TailwindDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Register the Tailwind device, since other entities will have it as a parent.
    # This prevents a child device being created before the parent ending up
    # with a missing via_device.
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, coordinator.data.device_id)},
        connections={(dr.CONNECTION_NETWORK_MAC, coordinator.data.mac_address)},
        manufacturer="Tailwind",
        model=coordinator.data.product,
        sw_version=coordinator.data.firmware_version,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Tailwind config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok

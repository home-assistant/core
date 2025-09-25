"""The Dynamic DNS integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .coordinator import DynamicDnsConfigEntry, DynamicDnsUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: DynamicDnsConfigEntry) -> bool:
    """Set up Dynamic DNS from a config entry."""

    coordinator = DynamicDnsUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    entry.async_on_unload(coordinator.async_add_listener(lambda: None))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DynamicDnsConfigEntry) -> bool:
    """Unload a config entry."""
    return True

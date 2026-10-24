"""The Hitron CODA integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import HitronCodaConfigEntry, HitronCodaDataUpdateCoordinator

PLATFORMS = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, entry: HitronCodaConfigEntry) -> None:
    """Set up the router from a config entry."""
    coordinator = HitronCodaDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: HitronCodaConfigEntry) -> None:
    """Unload the router and its device trackers."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

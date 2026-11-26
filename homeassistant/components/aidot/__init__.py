"""The aidot integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, async_noop

from .coordinator import AidotConfigEntry, AidotDeviceManagerCoordinator

PLATFORMS: list[Platform] = [Platform.LIGHT]


async def async_setup_entry(hass: HomeAssistant, entry: AidotConfigEntry) -> None:
    """Set up aidot from a config entry."""

    coordinator = AidotDeviceManagerCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(coordinator.async_add_listener(async_noop))


async def async_unload_entry(hass: HomeAssistant, entry: AidotConfigEntry) -> None:
    """Unload a config entry."""
    await entry.runtime_data.async_cleanup()
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

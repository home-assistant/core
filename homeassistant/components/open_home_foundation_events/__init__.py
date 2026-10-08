"""The Open Home Foundation Events integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import OHFEventsConfigEntry, OHFEventsCoordinator

_PLATFORMS: list[Platform] = [Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: OHFEventsConfigEntry) -> bool:
    """Set up Open Home Foundation Events from a config entry."""
    coordinator = OHFEventsCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OHFEventsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: OHFEventsConfigEntry
) -> None:
    """Reload the entry when areas are added, changed or removed."""
    hass.config_entries.async_schedule_reload(entry.entry_id)

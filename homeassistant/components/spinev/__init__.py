"""The Spin EV Charger integration."""

from homeassistant.core import HomeAssistant

from .const import PLATFORMS
from .coordinator import SpinEvConfigEntry, SpinEvCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: SpinEvConfigEntry) -> bool:
    """Set up a charger from a config entry."""
    coordinator = SpinEvCoordinator(hass, entry)
    entry.async_on_unload(coordinator.async_release)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: SpinEvConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: SpinEvConfigEntry) -> None:
    """Reload the entry so a changed connection mode takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)

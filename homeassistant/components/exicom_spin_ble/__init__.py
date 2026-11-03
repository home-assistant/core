"""The Spin EV Charger integration."""

from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant

from .const import PLATFORMS
from .coordinator import SpinEvConfigEntry, SpinEvCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: SpinEvConfigEntry) -> None:
    """Set up a charger from a config entry."""
    coordinator = SpinEvCoordinator(hass, entry)

    # The coordinator shuts itself down on unload, but not on stop.
    async def _async_stop(event: Event) -> None:
        await coordinator.async_shutdown()

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _async_stop)
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: SpinEvConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: SpinEvConfigEntry) -> None:
    """Reload the entry so a changed connection mode takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)

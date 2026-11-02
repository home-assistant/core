"""The Seafile integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback

from .const import DATA_BACKUP_AGENT_LISTENERS
from .coordinator import SeafileConfigEntry, SeafileDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BUTTON, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: SeafileConfigEntry) -> None:
    """Set up Seafile from a config entry."""
    coordinator = SeafileDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Adding or removing a library subentry reloads the entry.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    @callback
    def _async_notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(_async_notify_backup_listeners))


async def async_unload_entry(hass: HomeAssistant, entry: SeafileConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant, entry: SeafileConfigEntry
) -> None:
    """Reload the entry after its subentries changed."""
    await hass.config_entries.async_reload(entry.entry_id)

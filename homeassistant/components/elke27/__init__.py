"""Set up the Elke27 integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .coordinator import Elke27DataUpdateCoordinator
from .helpers import device_info_for_entry
from .models import Elke27ConfigEntry, Elke27RuntimeData

PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
]


async def async_setup_entry(hass: HomeAssistant, entry: Elke27ConfigEntry) -> bool:
    """Set up Elke27 from a config entry."""
    coordinator = Elke27DataUpdateCoordinator(hass, entry)
    entry.async_on_unload(coordinator.async_disconnect)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = Elke27RuntimeData(coordinator=coordinator)
    _async_register_panel_device(hass, coordinator, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


def _async_register_panel_device(
    hass: HomeAssistant,
    coordinator: Elke27DataUpdateCoordinator,
    entry: Elke27ConfigEntry,
) -> None:
    """Register the panel device for area devices to reference."""
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        **device_info_for_entry(coordinator, entry),
    )


async def async_unload_entry(hass: HomeAssistant, entry: Elke27ConfigEntry) -> bool:
    """Unload an Elke27 config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

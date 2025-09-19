"""The ToGrill integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import DeviceNotFound, ToGrillConfigEntry, ToGrillCoordinator

_PLATFORMS: list[Platform] = [
    Platform.EVENT,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.NUMBER,
]


async def async_setup_entry(hass: HomeAssistant, entry: ToGrillConfigEntry) -> bool:
    """Set up ToGrill Bluetooth from a config entry."""

    coordinator = ToGrillCoordinator(hass, entry)
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady as exc:
        if not isinstance(exc.__cause__, DeviceNotFound):
            raise

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ToGrillConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

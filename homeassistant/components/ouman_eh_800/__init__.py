"""The Ouman EH-800 integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import OumanEh800ConfigEntry, OumanEh800Coordinator

_PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.VALVE,
]


async def async_setup_entry(hass: HomeAssistant, entry: OumanEh800ConfigEntry) -> bool:
    """Set up Ouman EH-800 from a config entry."""
    coordinator = OumanEh800Coordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()
    coordinator.sync_circuit_device_names()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OumanEh800ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

"""The Flexit Nordic (BACnet) integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import FlexitConfigEntry, FlexitCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: FlexitConfigEntry) -> None:
    """Set up Flexit Nordic (BACnet) from a config entry."""

    coordinator = FlexitCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: FlexitConfigEntry) -> None:
    """Unload the Flexit Nordic (BACnet) config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

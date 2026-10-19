"""The Starlink integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import StarlinkConfigEntry, StarlinkUpdateCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TIME,
]


async def async_setup_entry(
    hass: HomeAssistant, config_entry: StarlinkConfigEntry
) -> None:
    """Set up Starlink from a config entry."""
    config_entry.runtime_data = StarlinkUpdateCoordinator(hass, config_entry)
    await config_entry.runtime_data.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: StarlinkConfigEntry
) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)

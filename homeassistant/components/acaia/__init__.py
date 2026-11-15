"""Initialize the Acaia component."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import AcaiaConfigEntry, AcaiaCoordinator

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: AcaiaConfigEntry) -> None:
    """Set up acaia as config entry."""

    coordinator = AcaiaCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: AcaiaConfigEntry) -> None:
    """Unload a config entry."""

    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    # Changing the options reloads the entry, so the connection has to be released.
    await entry.runtime_data.async_stop()

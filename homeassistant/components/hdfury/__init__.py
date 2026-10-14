"""The HDFury Integration."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import HDFuryConfigEntry, HDFuryCoordinator

PLATFORMS = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: HDFuryConfigEntry) -> None:
    """Set up HDFury as config entry."""

    coordinator = HDFuryCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: HDFuryConfigEntry) -> None:
    """Unload a HDFury config entry."""

    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

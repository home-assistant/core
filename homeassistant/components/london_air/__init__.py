"""The london_air component."""

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import LondonAirConfigEntry, LondonAirCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: LondonAirConfigEntry) -> None:
    """Set up London Air from a config entry."""
    coordinator = LondonAirCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: LondonAirConfigEntry) -> None:
    """Unload a London Air config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

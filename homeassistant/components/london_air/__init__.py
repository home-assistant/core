"""The london_air component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .sensor import APIData

type LondonAirConfigEntry = ConfigEntry[APIData]

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: LondonAirConfigEntry) -> None:
    """Set up London Air from a config entry."""
    api_data = APIData(hass)
    await api_data.async_update()
    entry.runtime_data = api_data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: LondonAirConfigEntry) -> None:
    """Unload a London Air config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)

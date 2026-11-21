"""The tcp component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_VALUE_ON

type TcpConfigEntry = ConfigEntry[list[Platform]]


async def async_setup_entry(hass: HomeAssistant, entry: TcpConfigEntry) -> None:
    """Set up TCP from a config entry."""
    platforms = [Platform.SENSOR]
    if CONF_VALUE_ON in entry.data:
        platforms.append(Platform.BINARY_SENSOR)
    entry.runtime_data = platforms
    await hass.config_entries.async_forward_entry_setups(entry, platforms)


async def async_unload_entry(hass: HomeAssistant, entry: TcpConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, entry.runtime_data)

"""The universal component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

DOMAIN = "universal"
_PLATFORMS = (Platform.MEDIA_PLAYER,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up Universal media player from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a Universal media player config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, _PLATFORMS)

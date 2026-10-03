"""The universal component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

DOMAIN = "universal"
_PLATFORMS = (Platform.MEDIA_PLAYER,)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Universal media player from a config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Universal media player config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)

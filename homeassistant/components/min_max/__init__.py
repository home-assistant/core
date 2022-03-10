"""The min_max component."""
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TYPE, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_ENTITY_IDS

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Min/Max from a config entry."""
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    return unload_ok


def get_unique_id(data: dict[str, Any]) -> str:
    """Get unique ID for a list of entity IDs."""
    return f"{data[CONF_TYPE]}_{'_'.join(sorted(data[CONF_ENTITY_IDS]))}"

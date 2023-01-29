# """Initialize onetracker sensor platform."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hello World from a config entry."""

    hass.config_entries.async_setup_platforms(entry, ["sensor"])
    return True

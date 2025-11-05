"""The RYSE integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up RYSE."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

"""The nederlandse_spoorwegen component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NS API as config entry."""
    print("test_init")
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

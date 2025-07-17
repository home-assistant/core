"""The wsdot component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up wsdot as config entry."""
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True

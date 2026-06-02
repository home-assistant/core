"""The arwn component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .sensor import ArwnSensor

type ArwnConfigEntry = ConfigEntry[dict[str, ArwnSensor]]

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ArwnConfigEntry) -> bool:
    """Set up ARWN from a config entry."""
    entry.runtime_data = {}
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ArwnConfigEntry) -> bool:
    """Unload ARWN config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

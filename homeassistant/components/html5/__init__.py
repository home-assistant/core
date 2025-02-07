"""The html5 component."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HTML5 from a config entry."""
    await discovery.async_load_platform(
        hass, Platform.NOTIFY, DOMAIN, dict(entry.data), {}
    )
    return True

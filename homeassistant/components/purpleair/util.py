"""Define PurpleAir utilities."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@callback
def async_get_config_entries_by_api_key(
    hass: HomeAssistant, api_key: str
) -> list[ConfigEntry]:
    """Get all ConfigEntry objects whose data contains an API key."""
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.data[CONF_API_KEY] == api_key
    ]

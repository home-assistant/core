"""Helpers for Prowl tests."""

from homeassistant.components.prowl.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant


def get_config_entry(
    hass: HomeAssistant,
    api_key: str,
    name: str | None = None,
    config_method: str | None = None,
) -> ConfigEntry | None:
    """Get the Prowl config entry with the specified API key."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get(CONF_API_KEY) == api_key:
            if name and entry.title != name:
                continue
            if config_method and entry.source != config_method:
                continue
            return entry
    return None

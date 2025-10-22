"""Diagnostics support for OpenH264 Nedis Camera integration."""
from __future__ import annotations
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry):
    """Return diagnostics for a config entry."""
    data = dict(entry.data)
    options = dict(entry.options)
    
    # Redact sensitive fields
    for key in ["username", "password", "token", "api_key"]:
        if key in data:
            data[key] = "***REDACTED***"
        if key in options:
            options[key] = "***REDACTED***"
    
    # Get encoder availability
    encoder_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    encoder = encoder_data.get("encoder")
    encoder_available = encoder.available if encoder else False
    
    return {
        "data": data,
        "options": options,
        "encoder_available": encoder_available,
        "entry_id": entry.entry_id,
        "title": entry.title,
        "state": entry.state.value if entry.state else "unknown"
    }

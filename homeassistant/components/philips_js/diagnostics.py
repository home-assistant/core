"""Diagnostics support for Philips JS."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import PhilipsTVConfigEntry

TO_REDACT = {
    "serialnumber_encrypted",
    "serialnumber",
    "deviceid_encrypted",
    "deviceid",
    "username",
    "password",
    "title",
    "unique_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PhilipsTVConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    api = coordinator.api

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": {
            "system": async_redact_data(api.system, TO_REDACT),
            "powerstate": api.powerstate,
            "context": api.context,
            "application": api.application,
            "applications": api.applications,
            "source_id": api.source_id,
            "sources": api.sources,
            "ambilight_styles": api.ambilight_styles,
            "ambilight_topology": api.ambilight_topology,
            "ambilight_current_configuration": api.ambilight_current_configuration,
            "ambilight_mode_raw": api.ambilight_mode_raw,
            "ambilight_modes": api.ambilight_modes,
            "ambilight_power_raw": api.ambilight_power_raw,
            "ambilight_power": api.ambilight_power,
            "ambilight_cached": api.ambilight_cached,
            "ambilight_measured": api.ambilight_measured,
            "ambilight_processed": api.ambilight_processed,
            "screenstate": api.screenstate,
            "on": api.on,
            "channel": api.channel,
            "channels": api.channels,
            "channel_lists": api.channel_lists,
            "favorite_lists": api.favorite_lists,
        },
    }

"""Diagnostics support for Cloudflare Workers AI."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_API_TOKEN, CONF_GATEWAY_API_TOKEN

TO_REDACT = {CONF_API_TOKEN, CONF_GATEWAY_API_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    subentries = []
    for subentry_id, subentry in entry.subentries.items():
        subentries.append(
            {
                "subentry_id": subentry_id,
                "subentry_type": subentry.subentry_type,
                "title": subentry.title,
                "data": dict(subentry.data),
            }
        )

    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "subentries": subentries,
    }

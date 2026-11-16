"""Diagnostics support for Seafile."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_TOKEN, CONF_URL
from homeassistant.core import HomeAssistant

from .coordinator import SeafileConfigEntry

TO_REDACT = {
    CONF_TOKEN,
    CONF_URL,
    "modifier_email",
    "modifier_name",
    "owner",
    "owner_name",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SeafileConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return async_redact_data(
        {
            "entry_data": dict(entry.data),
            "subentries": {
                subentry.subentry_id: {
                    "title": subentry.title,
                    "subentry_type": subentry.subentry_type,
                    "data": dict(subentry.data),
                }
                for subentry in entry.subentries.values()
            },
            "coordinator_data": asdict(entry.runtime_data.data),
        },
        TO_REDACT,
    )

"""Provides diagnostics for google calendar."""

import datetime
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .store import GoogleConfigEntry

TO_REDACT = {
    "id",
    "ical_uuid",
    "summary",
    "description",
    "location",
    "attendees",
    "recurring_event_id",
}


def redact_store(data: dict[str, Any]) -> dict[str, Any]:
    """Redact personal information from calendar events in the store."""
    id_num = 0
    diagnostics = {}
    for store_data in data.values():
        local_store: dict[str, Any] = store_data.get("event_sync", {})
        for calendar_data in local_store.values():
            id_num += 1
            items: dict[str, Any] = calendar_data.get("items", {})
            diagnostics[f"calendar#{id_num}"] = {
                "events": [
                    async_redact_data(item, TO_REDACT) for item in items.values()
                ],
                "sync_token_version": calendar_data.get("sync_token_version"),
            }
    return diagnostics


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: GoogleConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    payload: dict[str, Any] = {
        "now": dt_util.now().isoformat(),
        "timezone": str(dt_util.get_default_time_zone()),
        "system_timezone": str(datetime.datetime.now().astimezone().tzinfo),
    }

    store = config_entry.runtime_data.store
    if data := await store.async_load():
        payload["store"] = redact_store(data)
    return payload

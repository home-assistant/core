"""Provides diagnostics for google calendar."""

from typing import Any

from gcal_sync.const import EVENT_SYNC

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
    local_store: dict[str, Any] = data.get(EVENT_SYNC, {})
    return {
        f"calendar#{id_num}": {
            "events": [
                async_redact_data(item, TO_REDACT)
                for item in calendar_data.get("items", {}).values()
            ],
            "sync_token_version": calendar_data.get("sync_token_version"),
        }
        for id_num, calendar_data in enumerate(local_store.values(), start=1)
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: GoogleConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    payload: dict[str, Any] = {
        "now": dt_util.now().isoformat(),
        "timezone": str(dt_util.get_default_time_zone()),
        "system_timezone": str(dt_util.naive_now().astimezone().tzinfo),
    }

    store = config_entry.runtime_data.store
    if data := await store.async_load():
        payload["store"] = redact_store(data)
    return payload

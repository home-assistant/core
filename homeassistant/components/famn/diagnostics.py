"""Diagnostics support for the Famn integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import FamnConfigEntry

TO_REDACT = {
    "created_by",
    "updated_by",
    "executing_user_id",
    "assignments",
    "organizer",
    "ics_blob",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FamnConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "chore_lists": [
            {
                "task_list": async_redact_data(
                    chore_list.task_list.to_dict(), TO_REDACT
                ),
                "items": [
                    async_redact_data(item.to_dict(), TO_REDACT)
                    for item in chore_list.items
                ],
            }
            for chore_list in entry.runtime_data.chores.data.values()
        ],
        "calendars": [
            {
                "calendar": async_redact_data(
                    calendar_data.calendar.to_dict(), TO_REDACT
                ),
                "upcoming": [
                    async_redact_data(event.to_dict(), TO_REDACT)
                    for event in calendar_data.upcoming
                ],
            }
            for calendar_data in entry.runtime_data.calendars.data.values()
        ],
    }

"""Diagnostics support for SmartTub."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .const import ATTR_ERRORS, ATTR_REMINDERS, ATTR_STATUS
from .controller import SmartTubConfigEntry

TO_REDACT = {
    CONF_EMAIL,
    CONF_PASSWORD,
    "address",
    "panelSerialNumber",
    "spaId",
    "ssid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SmartTubConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    controller = entry.runtime_data

    return {
        "config_entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "spas": [
            {
                "status": async_redact_data(
                    spa_data[ATTR_STATUS].properties, TO_REDACT
                ),
                "reminders": [
                    {
                        "name": reminder.name,
                        "remaining_days": reminder.remaining_days,
                        "snoozed": reminder.snoozed,
                    }
                    for reminder in spa_data[ATTR_REMINDERS].values()
                ],
                "errors": [
                    {
                        "code": error.code,
                        "title": error.title,
                        "description": error.description,
                        "error_type": error.error_type,
                        "created_at": error.created_at.isoformat(),
                        "updated_at": error.updated_at.isoformat(),
                    }
                    for error in spa_data[ATTR_ERRORS]
                ],
            }
            for spa_data in (controller.coordinator.data or {}).values()
        ],
    }

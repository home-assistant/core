"""Diagnostics for bosch alarm."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import BoschAlarmConfigEntry
from .const import CONF_INSTALLER_CODE, CONF_USER_CODE

TO_REDACT = [CONF_INSTALLER_CODE, CONF_USER_CODE, CONF_PASSWORD]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BoschAlarmConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "data": {
            "model": entry.runtime_data.model,
            "serial_number": entry.runtime_data.serial_number,
            "protocol_version": entry.runtime_data.protocol_version,
            "firmware_version": entry.runtime_data.firmware_version,
            "areas": [
                {
                    "id": area_id,
                    "name": area.name,
                    "all_ready": area.all_ready,
                    "part_ready": area.part_ready,
                    "faults": area.faults,
                    "alarms": area.alarms,
                    "disarmed": area.is_disarmed(),
                    "arming": area.is_arming(),
                    "pending": area.is_pending(),
                    "part_armed": area.is_part_armed(),
                    "all_armed": area.is_all_armed(),
                    "armed": area.is_armed(),
                    "triggered": area.is_triggered(),
                }
                for area_id, area in entry.runtime_data.areas.items()
            ],
            "points": [
                {
                    "id": point_id,
                    "name": point.name,
                    "open": point.is_open(),
                    "normal": point.is_normal(),
                }
                for point_id, point in entry.runtime_data.points.items()
            ],
            "doors": [
                {
                    "id": door_id,
                    "name": door.name,
                    "open": door.is_open(),
                    "locked": door.is_locked(),
                }
                for door_id, door in entry.runtime_data.doors.items()
            ],
            "outputs": [
                {
                    "id": output_id,
                    "name": output.name,
                    "active": output.is_active(),
                }
                for output_id, output in entry.runtime_data.outputs.items()
            ],
            "history_events": entry.runtime_data.events,
        },
    }

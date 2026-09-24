"""Diagnostics support for Rain Bird."""

from dataclasses import asdict
import datetime
from typing import Any

from pyrainbird.const import DayOfWeek
from pyrainbird.data import Schedule

from homeassistant.core import HomeAssistant

from .types import RainbirdConfigEntry


def _minutes(duration: datetime.timedelta) -> int:
    return int(duration.total_seconds() // 60)


def _days(days_of_week: set[DayOfWeek]) -> list[str]:
    return [day.name for day in sorted(days_of_week)]


def _starts(starts: list[datetime.time]) -> list[str]:
    return [start.strftime("%H:%M") for start in starts]


def _schedule(schedule: Schedule) -> dict[str, Any]:
    # The library's to_dict() does not support the schedule's time fields.
    return {
        "controller_info": (
            asdict(schedule.controller_info) if schedule.controller_info else None
        ),
        "programs": [
            {
                "program": program.name,
                "frequency": program.frequency.name,
                "days_of_week": _days(program.days_of_week),
                "period": program.period,
                "synchro": program.synchro,
                "starts": _starts(program.starts),
                "zone_minutes": {
                    zone.name: _minutes(zone.duration) for zone in program.durations
                },
            }
            for program in schedule.programs
        ],
        "zone_schedules": [
            {
                "zone": zone.zone,
                "frequency": zone.frequency.name,
                "days_of_week": _days(zone.days_of_week),
                "period": zone.period,
                "synchro": zone.synchro,
                "starts": _starts(zone.starts),
                "minutes": _minutes(zone.duration),
            }
            for zone in schedule.zone_schedules.values()
        ],
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RainbirdConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    model = data.model_info
    state = data.coordinator.data
    schedule = data.schedule_coordinator.data
    return {
        "options": dict(entry.options),
        "model": {
            "model": f"{model.model:04X}",
            "name": model.model_name,
            "firmware": f"{model.major}.{model.minor}",
            "max_programs": model.model_info.max_programs,
            "max_stations": model.model_info.max_stations,
        },
        "state": {
            "zones": sorted(state.zones),
            "active_zones": sorted(state.active_zones),
            "rain": state.rain,
            "rain_delay": state.rain_delay,
        },
        "schedule": _schedule(schedule) if schedule else None,
    }

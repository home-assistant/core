"""Build and save firewall policy schedules for UniFi Network.

The controller stores schedule keys the current mode doesn't use, so a
schedule is always built from scratch with exactly the keys its mode needs.
"""

from collections.abc import Mapping
from datetime import date, time
from typing import TYPE_CHECKING, Any, NoReturn

from aiounifi.models.firewall_policy import (
    FirewallPolicy,
    FirewallPolicySchedule,
    FirewallPolicyScheduleMode,
)

from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import DOMAIN

if TYPE_CHECKING:
    from .hub import UnifiHub

# The UniFi Network UI fills these in when a mode needs times.
DEFAULT_TIME_RANGE_START = "09:00"
DEFAULT_TIME_RANGE_END = "12:00"

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

MODES_WITH_DAYS = (
    FirewallPolicyScheduleMode.EVERY_WEEK,
    FirewallPolicyScheduleMode.CUSTOM,
)
MODES_WITH_START_DATE = (
    FirewallPolicyScheduleMode.ONE_TIME_ONLY,
    FirewallPolicyScheduleMode.CUSTOM,
)
MODES_WITHOUT_SETTINGS = (
    FirewallPolicyScheduleMode.ALWAYS,
    FirewallPolicyScheduleMode.UNKNOWN,
)


def policy_schedule(policy: FirewallPolicy) -> FirewallPolicySchedule:
    """Return a policy's schedule, or an unknown one if it has none."""
    # aiounifi types the schedule as always present; read it as optional.
    raw: Mapping[str, Any] = policy.raw
    schedule: FirewallPolicySchedule | None = raw.get("schedule")
    if schedule is None:
        return {"mode": FirewallPolicyScheduleMode.UNKNOWN.value}
    return schedule


def schedule_mode(schedule: FirewallPolicySchedule) -> FirewallPolicyScheduleMode:
    """Return a schedule's mode."""
    return FirewallPolicyScheduleMode(schedule.get("mode"))


def schedule_uses_times(schedule: FirewallPolicySchedule) -> bool:
    """Return whether the schedule has a start and end time."""
    mode = schedule_mode(schedule)
    if mode in MODES_WITHOUT_SETTINGS:
        return False
    return not (mode in MODES_WITH_DAYS and schedule.get("time_all_day") is True)


def parse_time(value: object) -> time | None:
    """Parse the controller's HH:MM, or return None if it is malformed."""
    if not isinstance(value, str):
        return None
    hour, _, minute = value.partition(":")
    try:
        return time(int(hour), int(minute))
    except ValueError:
        return None


def parse_date(value: object) -> date | None:
    """Parse the controller's YYYY-MM-DD, or return None if it is malformed."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def build_schedule(
    current: FirewallPolicySchedule,
    today: date,
    *,
    mode: FirewallPolicyScheduleMode | None = None,
    start: time | None = None,
    end: time | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> FirewallPolicySchedule:
    """Build the schedule for a mode from the current one plus changes.

    Values the new mode needs are taken from the changes, then from the
    current schedule, then from defaults. A date is only kept when the mode
    doesn't change: switching to a dated mode starts it today.
    """
    current_mode = schedule_mode(current)
    new_mode = mode or current_mode
    schedule: FirewallPolicySchedule = {"mode": new_mode.value}
    if new_mode in MODES_WITHOUT_SETTINGS:
        return schedule

    today_str = today.isoformat()
    same_mode = new_mode is current_mode
    # Read through a Mapping: a TypedDict only accepts literal keys.
    current_values: Mapping[str, object] = current

    def _date(changed: date | None, key: str) -> str:
        if changed is not None:
            return changed.isoformat()
        if same_mode and isinstance(kept := current_values.get(key), str):
            return kept
        return today_str

    all_day = False
    if new_mode in MODES_WITH_DAYS:
        days = current.get("repeat_on_days")
        chosen = [day for day in WEEKDAYS if isinstance(days, list) and day in days]
        schedule["repeat_on_days"] = chosen or list(WEEKDAYS)
        all_day = (
            current_mode in MODES_WITH_DAYS and current.get("time_all_day") is True
        )
        schedule["time_all_day"] = all_day
    if new_mode is FirewallPolicyScheduleMode.ONE_TIME_ONLY:
        schedule["date"] = _date(start_date, "date")
    if new_mode is FirewallPolicyScheduleMode.CUSTOM:
        schedule["date_start"] = _date(start_date, "date_start")
        schedule["date_end"] = _date(end_date, "date_end")
    if not all_day:
        schedule["time_range_start"] = (
            start.strftime("%H:%M")
            if start is not None
            else current.get("time_range_start", DEFAULT_TIME_RANGE_START)
        )
        schedule["time_range_end"] = (
            end.strftime("%H:%M")
            if end is not None
            else current.get("time_range_end", DEFAULT_TIME_RANGE_END)
        )
    return schedule


def raise_setting_unused() -> NoReturn:
    """Raise because the policy's schedule mode doesn't use a setting."""
    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="schedule_setting_unused_in_mode",
    )


async def async_save_schedule(
    hub: UnifiHub,
    obj_id: str,
    *,
    mode: FirewallPolicyScheduleMode | None = None,
    start: time | None = None,
    end: time | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> None:
    """Save a change to a firewall policy's schedule.

    "Today" is the controller's date: its clock is the one the schedule runs on.
    """
    policy = hub.api.firewall_policies[obj_id]
    schedule = build_schedule(
        policy_schedule(policy),
        dt_util.now(hub.time_zone).date(),
        mode=mode,
        start=start,
        end=end,
        start_date=start_date,
        end_date=end_date,
    )
    await hub.api.firewall_policies.save(policy, schedule=schedule)

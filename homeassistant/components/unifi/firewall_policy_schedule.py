"""Build and save firewall policy schedules for UniFi Network.

The controller stores schedule keys the current mode doesn't use, so a
schedule is always built from scratch with exactly the keys its mode needs.
"""

from collections.abc import Collection, Mapping
from datetime import date, time, timedelta
from typing import TYPE_CHECKING, Any, NoReturn

from aiounifi.models.firewall_policy import (
    FirewallPolicy,
    FirewallPolicySchedule,
    FirewallPolicyScheduleMode,
)

from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MODES_WITH_DAYS

if TYPE_CHECKING:
    from .hub import UnifiHub

# The UniFi Network UI fills these in when a mode needs times.
DEFAULT_TIME_RANGE_START = "09:00"
DEFAULT_TIME_RANGE_END = "12:00"

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

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


def schedule_days(schedule: FirewallPolicySchedule) -> list[str]:
    """Return the schedule's selected days of the week, Monday first."""
    days = schedule.get("repeat_on_days")
    if not isinstance(days, list):
        return []
    return [day for day in WEEKDAYS if day in days]


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
    all_day: bool | None = None,
    days: Collection[str] | None = None,
) -> FirewallPolicySchedule:
    """Build the schedule for a mode from the current one plus changes.

    Times are taken from the changes, then from the current schedule if it
    uses them, then from defaults; a malformed stored time or date is replaced
    the same way a missing one is. Dates and days are only kept when the mode
    doesn't change: choosing a mode starts it today, on every day of the week,
    with a time window.
    """
    current_mode = schedule_mode(current)
    new_mode = mode or current_mode
    schedule: FirewallPolicySchedule = {"mode": new_mode.value}
    if new_mode in MODES_WITHOUT_SETTINGS:
        return schedule

    same_mode = new_mode is current_mode
    # The controller keeps the times of a schedule that doesn't use them.
    keep_times = schedule_uses_times(current)
    # Read through a Mapping: a TypedDict only accepts literal keys.
    current_values: Mapping[str, object] = current

    def _date(
        changed: date | None, key: str, *, keep: bool, default: date = today
    ) -> date:
        if changed is not None:
            return changed
        if keep and (kept := parse_date(current_values.get(key))) is not None:
            return kept
        return default

    def _time(changed: time | None, key: str, default: str) -> str:
        # A malformed stored time is replaced, so it isn't sent back.
        if changed is None and keep_times:
            changed = parse_time(current_values.get(key))
        return default if changed is None else changed.strftime("%H:%M")

    all_day_on = False
    if new_mode in MODES_WITH_DAYS:
        if same_mode:
            # A value change leaves the days alone, even if none are chosen.
            selected = schedule_days(current) if days is None else days
            schedule["repeat_on_days"] = [day for day in WEEKDAYS if day in selected]
            all_day_on = (
                current.get("time_all_day") is True if all_day is None else all_day
            )
        else:
            schedule["repeat_on_days"] = list(WEEKDAYS)
        schedule["time_all_day"] = all_day_on
    if new_mode is FirewallPolicyScheduleMode.ONE_TIME_ONLY:
        # Choosing One time, even again, dates it today.
        schedule["date"] = _date(start_date, "date", keep=mode is None).isoformat()
    if new_mode is FirewallPolicyScheduleMode.CUSTOM:
        first_day = _date(start_date, "date_start", keep=same_mode)
        last_day = _date(
            end_date, "date_end", keep=same_mode, default=today + timedelta(days=1)
        )
        # The controller requires the range to end after the day it starts.
        if first_day >= last_day:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="schedule_dates_out_of_order",
            )
        schedule["date_start"] = first_day.isoformat()
        schedule["date_end"] = last_day.isoformat()
    if not all_day_on:
        schedule["time_range_start"] = _time(
            start, "time_range_start", DEFAULT_TIME_RANGE_START
        )
        schedule["time_range_end"] = _time(
            end, "time_range_end", DEFAULT_TIME_RANGE_END
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
    all_day: bool | None = None,
    days: Collection[str] | None = None,
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
        all_day=all_day,
        days=days,
    )
    await hub.api.firewall_policies.save(policy, schedule=schedule)

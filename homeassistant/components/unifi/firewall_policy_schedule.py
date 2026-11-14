"""Save firewall policy schedule changes for UniFi Network."""

from collections.abc import Mapping
from datetime import date, time
from typing import TYPE_CHECKING, Any

from aiounifi.models.firewall_policy import (
    FirewallPolicyScheduleError,
    FirewallPolicyScheduleMode,
    ScheduleDatesOutOfOrderError,
    ScheduleSettingUnusedError,
    build_schedule,
)

from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import DOMAIN

if TYPE_CHECKING:
    from .hub import UnifiHub

SCHEDULE_ERROR_TRANSLATION_KEYS: dict[type[FirewallPolicyScheduleError], str] = {
    ScheduleDatesOutOfOrderError: "schedule_dates_out_of_order",
    ScheduleSettingUnusedError: "schedule_setting_unused_in_mode",
}


async def async_save_schedule(
    hub: UnifiHub,
    obj_id: str,
    *,
    mode: FirewallPolicyScheduleMode | None = None,
    start_time: time | None = None,
    end_time: time | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> None:
    """Save a change to a firewall policy's schedule.

    "Today" is the controller's date: its clock is the one the schedule runs on.
    """
    policy = hub.api.firewall_policies[obj_id]
    # aiounifi types the schedule as always present; read it as optional.
    raw: Mapping[str, Any] = policy.raw
    try:
        schedule = build_schedule(
            raw.get("schedule", {}),
            dt_util.now(hub.time_zone).date(),
            mode=mode,
            start_time=start_time,
            end_time=end_time,
            start_date=start_date,
            end_date=end_date,
        )
    except FirewallPolicyScheduleError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=SCHEDULE_ERROR_TRANSLATION_KEYS[type(err)],
        ) from err
    await hub.api.firewall_policies.save(policy, schedule=schedule)

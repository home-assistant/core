"""Save firewall policy schedule changes for UniFi Network."""

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from aiounifi.models.firewall_policy import FirewallPolicyScheduleMode, build_schedule

from homeassistant.util import dt as dt_util

if TYPE_CHECKING:
    from .hub import UnifiHub


async def async_save_schedule(
    hub: UnifiHub,
    obj_id: str,
    *,
    mode: FirewallPolicyScheduleMode | None = None,
) -> None:
    """Save a change to a firewall policy's schedule.

    "Today" is the controller's date: its clock is the one the schedule runs on.
    """
    policy = hub.api.firewall_policies[obj_id]
    # aiounifi types the schedule as always present; read it as optional.
    raw: Mapping[str, Any] = policy.raw
    schedule = build_schedule(
        raw.get("schedule", {}),
        dt_util.now(hub.time_zone).date(),
        mode=mode,
    )
    await hub.api.firewall_policies.save(policy, schedule=schedule)

"""Time platform for UniFi Network integration.

Support for the start and end times of firewall policy schedules.
"""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import time
from typing import TYPE_CHECKING, Any, Literal, override

import aiounifi
from aiounifi.interfaces.api_handlers import APIHandler, ItemEvent
from aiounifi.interfaces.firewall_policies import FirewallPolicies
from aiounifi.models.api import ApiItem
from aiounifi.models.firewall_policy import FirewallPolicy

from homeassistant.components.time import TimeEntity, TimeEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UnifiConfigEntry
from .const import DOMAIN
from .entity import UnifiEntity, UnifiEntityDescription
from .firewall_policy_schedule import (
    async_save_schedule,
    parse_time,
    policy_schedule,
    raise_setting_unused,
    schedule_uses_times,
)
from .switch import (
    async_firewall_policy_supported_fn,
    async_unifi_network_device_info_fn,
)

if TYPE_CHECKING:
    from .hub import UnifiHub

PARALLEL_UPDATES = 1

type ScheduleTime = Literal["start", "end"]


@callback
def async_firewall_policy_schedule_time_fn(
    which: ScheduleTime, hub: UnifiHub, policy: FirewallPolicy
) -> time | None:
    """Return a firewall policy schedule's start or end time."""
    schedule = policy_schedule(policy)
    if not schedule_uses_times(schedule):
        return None
    if which == "start":
        return parse_time(schedule.get("time_range_start"))
    return parse_time(schedule.get("time_range_end"))


async def async_firewall_policy_schedule_time_control_fn(
    which: ScheduleTime, hub: UnifiHub, obj_id: str, value: time
) -> None:
    """Change a firewall policy schedule's start or end time."""
    policy = hub.api.firewall_policies[obj_id]
    if not schedule_uses_times(policy_schedule(policy)):
        raise_setting_unused()
    if which == "start":
        await async_save_schedule(hub, obj_id, start=value)
    else:
        await async_save_schedule(hub, obj_id, end=value)


@dataclass(frozen=True, kw_only=True)
class UnifiTimeEntityDescription[HandlerT: APIHandler, ApiItemT: ApiItem](
    TimeEntityDescription, UnifiEntityDescription[HandlerT, ApiItemT]
):
    """Class describing UniFi time entity."""

    value_fn: Callable[[UnifiHub, ApiItemT], time | None]
    set_value_fn: Callable[[UnifiHub, str, time], Coroutine[Any, Any, None]]


def _schedule_time_description(
    which: ScheduleTime,
) -> UnifiTimeEntityDescription[FirewallPolicies, FirewallPolicy]:
    """Describe the start or end time of a firewall policy schedule."""

    @callback
    def value_fn(hub: UnifiHub, policy: FirewallPolicy) -> time | None:
        return async_firewall_policy_schedule_time_fn(which, hub, policy)

    async def set_value_fn(hub: UnifiHub, obj_id: str, value: time) -> None:
        await async_firewall_policy_schedule_time_control_fn(which, hub, obj_id, value)

    return UnifiTimeEntityDescription[FirewallPolicies, FirewallPolicy](
        key=f"Firewall policy schedule {which}",
        translation_key=f"firewall_policy_schedule_{which}",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        api_handler_fn=lambda api: api.firewall_policies,
        device_info_fn=async_unifi_network_device_info_fn,
        object_fn=lambda api, obj_id: api.firewall_policies[obj_id],
        set_value_fn=set_value_fn,
        supported_fn=async_firewall_policy_supported_fn,
        translation_placeholders_fn=lambda policy: {"policy_name": policy.name},
        unique_id_fn=lambda hub, obj_id: f"firewall_policy_schedule_{which}-{obj_id}",
        value_fn=value_fn,
    )


ENTITY_DESCRIPTIONS: tuple[UnifiTimeEntityDescription, ...] = (
    _schedule_time_description("start"),
    _schedule_time_description("end"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UnifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up time platform for UniFi Network integration."""
    config_entry.runtime_data.entity_loader.register_platform(
        async_add_entities, UnifiTimeEntity, ENTITY_DESCRIPTIONS, requires_admin=True
    )


class UnifiTimeEntity[HandlerT: APIHandler, ApiItemT: ApiItem](
    UnifiEntity[HandlerT, ApiItemT], TimeEntity
):
    """Base representation of a UniFi time."""

    entity_description: UnifiTimeEntityDescription[HandlerT, ApiItemT]

    @override
    async def async_set_value(self, value: time) -> None:
        """Change the time."""
        try:
            await self.entity_description.set_value_fn(self.hub, self._obj_id, value)
        except aiounifi.AiounifiException as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="action_request_failed",
            ) from err
        await self.async_refresh_after_control()

    @callback
    @override
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state."""
        description = self.entity_description
        obj = description.object_fn(self.api, self._obj_id)
        self._attr_native_value = description.value_fn(self.hub, obj)

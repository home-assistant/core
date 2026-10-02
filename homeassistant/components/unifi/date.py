"""Date platform for UniFi Network integration.

Support for the start and end dates of firewall policy schedules.
"""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any, override

import aiounifi
from aiounifi.interfaces.api_handlers import APIHandler, ItemEvent
from aiounifi.interfaces.firewall_policies import FirewallPolicies
from aiounifi.models.api import ApiItem
from aiounifi.models.firewall_policy import FirewallPolicy, FirewallPolicyScheduleMode

from homeassistant.components.date import DateEntity, DateEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UnifiConfigEntry
from .const import DOMAIN
from .entity import UnifiEntity, UnifiEntityDescription
from .firewall_policy_schedule import (
    MODES_WITH_START_DATE,
    async_save_schedule,
    parse_date,
    policy_schedule,
    raise_setting_unused,
    schedule_mode,
)
from .switch import (
    async_firewall_policy_supported_fn,
    async_unifi_network_device_info_fn,
)

if TYPE_CHECKING:
    from .hub import UnifiHub

PARALLEL_UPDATES = 1


@callback
def async_firewall_policy_schedule_start_date_fn(
    hub: UnifiHub, policy: FirewallPolicy
) -> date | None:
    """Return the date a firewall policy schedule starts on."""
    schedule = policy_schedule(policy)
    mode = schedule_mode(schedule)
    if mode is FirewallPolicyScheduleMode.ONE_TIME_ONLY:
        return parse_date(schedule.get("date"))
    if mode is FirewallPolicyScheduleMode.CUSTOM:
        return parse_date(schedule.get("date_start"))
    return None


@callback
def async_firewall_policy_schedule_end_date_fn(
    hub: UnifiHub, policy: FirewallPolicy
) -> date | None:
    """Return the date a firewall policy's custom schedule ends on."""
    schedule = policy_schedule(policy)
    if schedule_mode(schedule) is FirewallPolicyScheduleMode.CUSTOM:
        return parse_date(schedule.get("date_end"))
    return None


def _raise_if_out_of_order(start: date | None, end: date | None) -> None:
    """Raise if a custom schedule would end before it starts."""
    if start is not None and end is not None and start > end:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="schedule_dates_out_of_order",
        )


async def async_firewall_policy_schedule_start_date_control_fn(
    hub: UnifiHub, obj_id: str, value: date
) -> None:
    """Change the date a firewall policy schedule starts on."""
    schedule = policy_schedule(hub.api.firewall_policies[obj_id])
    mode = schedule_mode(schedule)
    if mode not in MODES_WITH_START_DATE:
        raise_setting_unused()
    if mode is FirewallPolicyScheduleMode.CUSTOM:
        _raise_if_out_of_order(value, parse_date(schedule.get("date_end")))
    await async_save_schedule(hub, obj_id, start_date=value)


async def async_firewall_policy_schedule_end_date_control_fn(
    hub: UnifiHub, obj_id: str, value: date
) -> None:
    """Change the date a firewall policy's custom schedule ends on."""
    schedule = policy_schedule(hub.api.firewall_policies[obj_id])
    if schedule_mode(schedule) is not FirewallPolicyScheduleMode.CUSTOM:
        raise_setting_unused()
    _raise_if_out_of_order(parse_date(schedule.get("date_start")), value)
    await async_save_schedule(hub, obj_id, end_date=value)


@dataclass(frozen=True, kw_only=True)
class UnifiDateEntityDescription[HandlerT: APIHandler, ApiItemT: ApiItem](
    DateEntityDescription, UnifiEntityDescription[HandlerT, ApiItemT]
):
    """Class describing UniFi date entity."""

    value_fn: Callable[[UnifiHub, ApiItemT], date | None]
    set_value_fn: Callable[[UnifiHub, str, date], Coroutine[Any, Any, None]]


ENTITY_DESCRIPTIONS: tuple[UnifiDateEntityDescription, ...] = (
    UnifiDateEntityDescription[FirewallPolicies, FirewallPolicy](
        key="Firewall policy schedule start date",
        translation_key="firewall_policy_schedule_start_date",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        api_handler_fn=lambda api: api.firewall_policies,
        device_info_fn=async_unifi_network_device_info_fn,
        object_fn=lambda api, obj_id: api.firewall_policies[obj_id],
        set_value_fn=async_firewall_policy_schedule_start_date_control_fn,
        supported_fn=async_firewall_policy_supported_fn,
        translation_placeholders_fn=lambda policy: {"policy_name": policy.name},
        unique_id_fn=lambda hub, obj_id: (
            f"firewall_policy_schedule_start_date-{obj_id}"
        ),
        value_fn=async_firewall_policy_schedule_start_date_fn,
    ),
    UnifiDateEntityDescription[FirewallPolicies, FirewallPolicy](
        key="Firewall policy schedule end date",
        translation_key="firewall_policy_schedule_end_date",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        api_handler_fn=lambda api: api.firewall_policies,
        device_info_fn=async_unifi_network_device_info_fn,
        object_fn=lambda api, obj_id: api.firewall_policies[obj_id],
        set_value_fn=async_firewall_policy_schedule_end_date_control_fn,
        supported_fn=async_firewall_policy_supported_fn,
        translation_placeholders_fn=lambda policy: {"policy_name": policy.name},
        unique_id_fn=lambda hub, obj_id: f"firewall_policy_schedule_end_date-{obj_id}",
        value_fn=async_firewall_policy_schedule_end_date_fn,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UnifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up date platform for UniFi Network integration."""
    config_entry.runtime_data.entity_loader.register_platform(
        async_add_entities, UnifiDateEntity, ENTITY_DESCRIPTIONS, requires_admin=True
    )


class UnifiDateEntity[HandlerT: APIHandler, ApiItemT: ApiItem](
    UnifiEntity[HandlerT, ApiItemT], DateEntity
):
    """Base representation of a UniFi date."""

    entity_description: UnifiDateEntityDescription[HandlerT, ApiItemT]

    @override
    async def async_set_value(self, value: date) -> None:
        """Change the date."""
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

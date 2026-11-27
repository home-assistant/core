"""Time platform for UniFi Network integration.

Support for the start and end times of firewall policy schedules.
"""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import time
from typing import TYPE_CHECKING, Any, override

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
from .entity import (
    UnifiEntity,
    UnifiEntityDescription,
    async_firewall_policy_device_info_fn,
    async_firewall_policy_supported_fn,
    async_save_firewall_policy_schedule,
)

if TYPE_CHECKING:
    from .hub import UnifiHub

PARALLEL_UPDATES = 1


@dataclass(frozen=True, kw_only=True)
class UnifiTimeEntityDescription[HandlerT: APIHandler, ApiItemT: ApiItem](
    TimeEntityDescription, UnifiEntityDescription[HandlerT, ApiItemT]
):
    """Class describing UniFi time entity."""

    value_fn: Callable[[UnifiHub, ApiItemT], time | None]
    set_value_fn: Callable[[UnifiHub, str, time], Coroutine[Any, Any, None]]


ENTITY_DESCRIPTIONS: tuple[UnifiTimeEntityDescription, ...] = (
    UnifiTimeEntityDescription[FirewallPolicies, FirewallPolicy](
        key="Firewall policy schedule start",
        translation_key="firewall_policy_schedule_start",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        api_handler_fn=lambda api: api.firewall_policies,
        device_info_fn=async_firewall_policy_device_info_fn,
        object_fn=lambda api, obj_id: api.firewall_policies[obj_id],
        set_value_fn=lambda hub, obj_id, value: async_save_firewall_policy_schedule(
            hub, obj_id, start_time=value
        ),
        supported_fn=async_firewall_policy_supported_fn,
        unique_id_fn=lambda hub, obj_id: f"firewall_policy_schedule_start-{obj_id}",
        value_fn=lambda hub, policy: policy.schedule_settings.start_time,
    ),
    UnifiTimeEntityDescription[FirewallPolicies, FirewallPolicy](
        key="Firewall policy schedule end",
        translation_key="firewall_policy_schedule_end",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        api_handler_fn=lambda api: api.firewall_policies,
        device_info_fn=async_firewall_policy_device_info_fn,
        object_fn=lambda api, obj_id: api.firewall_policies[obj_id],
        set_value_fn=lambda hub, obj_id, value: async_save_firewall_policy_schedule(
            hub, obj_id, end_time=value
        ),
        supported_fn=async_firewall_policy_supported_fn,
        unique_id_fn=lambda hub, obj_id: f"firewall_policy_schedule_end-{obj_id}",
        value_fn=lambda hub, policy: policy.schedule_settings.end_time,
    ),
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

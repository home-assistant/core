"""Select platform for UniFi Network integration.

Support for choosing the schedule mode of firewall policies.
"""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

import aiounifi
from aiounifi.interfaces.api_handlers import APIHandler, ItemEvent
from aiounifi.interfaces.firewall_policies import FirewallPolicies
from aiounifi.models.api import ApiItem
from aiounifi.models.firewall_policy import FirewallPolicy, FirewallPolicyScheduleMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UnifiConfigEntry
from .const import DOMAIN
from .entity import UnifiEntity, UnifiEntityDescription
from .firewall_policy_schedule import (
    MODES_WITH_DAYS,
    async_save_schedule,
    policy_schedule,
    schedule_mode,
)
from .switch import (
    async_firewall_policy_supported_fn,
    async_unifi_network_device_info_fn,
)

if TYPE_CHECKING:
    from .hub import UnifiHub

PARALLEL_UPDATES = 1

SCHEDULE_MODE_OPTIONS: dict[FirewallPolicyScheduleMode, str] = {
    FirewallPolicyScheduleMode.ALWAYS: "always",
    FirewallPolicyScheduleMode.EVERY_DAY: "every_day",
    FirewallPolicyScheduleMode.EVERY_WEEK: "every_week",
    FirewallPolicyScheduleMode.ONE_TIME_ONLY: "one_time",
    FirewallPolicyScheduleMode.CUSTOM: "custom",
}
SCHEDULE_OPTION_MODES = {option: mode for mode, option in SCHEDULE_MODE_OPTIONS.items()}


@callback
def async_firewall_policy_schedule_mode_fn(
    hub: UnifiHub, policy: FirewallPolicy
) -> str | None:
    """Return the option for a firewall policy's schedule mode."""
    return SCHEDULE_MODE_OPTIONS.get(schedule_mode(policy_schedule(policy)))


async def async_firewall_policy_schedule_mode_control_fn(
    hub: UnifiHub, obj_id: str, option: str
) -> None:
    """Change a firewall policy's schedule mode."""
    mode = SCHEDULE_OPTION_MODES[option]
    if mode in MODES_WITH_DAYS:
        # These modes need days of the week, which can't be chosen here yet.
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="schedule_mode_not_supported",
        )
    await async_save_schedule(hub, obj_id, mode=mode)


@dataclass(frozen=True, kw_only=True)
class UnifiSelectEntityDescription[HandlerT: APIHandler, ApiItemT: ApiItem](
    SelectEntityDescription, UnifiEntityDescription[HandlerT, ApiItemT]
):
    """Class describing UniFi select entity."""

    current_option_fn: Callable[[UnifiHub, ApiItemT], str | None]
    select_option_fn: Callable[[UnifiHub, str, str], Coroutine[Any, Any, None]]


ENTITY_DESCRIPTIONS: tuple[UnifiSelectEntityDescription, ...] = (
    UnifiSelectEntityDescription[FirewallPolicies, FirewallPolicy](
        key="Firewall policy schedule mode",
        translation_key="firewall_policy_schedule_mode",
        entity_category=EntityCategory.CONFIG,
        entity_registry_enabled_default=False,
        options=list(SCHEDULE_MODE_OPTIONS.values()),
        api_handler_fn=lambda api: api.firewall_policies,
        current_option_fn=async_firewall_policy_schedule_mode_fn,
        device_info_fn=async_unifi_network_device_info_fn,
        object_fn=lambda api, obj_id: api.firewall_policies[obj_id],
        select_option_fn=async_firewall_policy_schedule_mode_control_fn,
        supported_fn=async_firewall_policy_supported_fn,
        translation_placeholders_fn=lambda policy: {"policy_name": policy.name},
        unique_id_fn=lambda hub, obj_id: f"firewall_policy_schedule_mode-{obj_id}",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UnifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up select platform for UniFi Network integration."""
    config_entry.runtime_data.entity_loader.register_platform(
        async_add_entities, UnifiSelectEntity, ENTITY_DESCRIPTIONS, requires_admin=True
    )


class UnifiSelectEntity[HandlerT: APIHandler, ApiItemT: ApiItem](
    UnifiEntity[HandlerT, ApiItemT], SelectEntity
):
    """Base representation of a UniFi select."""

    entity_description: UnifiSelectEntityDescription[HandlerT, ApiItemT]

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        async with self.control_lock:
            try:
                await self.entity_description.select_option_fn(
                    self.hub, self._obj_id, option
                )
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
        self._attr_current_option = description.current_option_fn(self.hub, obj)

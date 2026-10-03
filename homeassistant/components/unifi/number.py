"""Number platform for UniFi Network integration.

Support for configuring failover priority and load balance weight of WAN networks.
"""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, override

from aiounifi.interfaces.api_handlers import APIHandler, ItemEvent
from aiounifi.interfaces.networks import Networks
from aiounifi.models.api import ApiItem
from aiounifi.models.network import Network

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UnifiConfigEntry
from .entity import (
    UnifiEntity,
    UnifiEntityDescription,
    async_wan_device_info_fn,
    wan_supported_fn,
)
from .hub import UnifiHub

PARALLEL_UPDATES = 1

# The controller accepts priorities beyond the number of WAN ports, and rejects
# duplicates itself, so the range is kept generous instead of second guessing it.
MAX_FAILOVER_PRIORITY = 10
MAX_LOAD_BALANCE_WEIGHT = 99


@dataclass(frozen=True, kw_only=True)
class UnifiNumberEntityDescription[HandlerT: APIHandler, ApiItemT: ApiItem](
    NumberEntityDescription, UnifiEntityDescription[HandlerT, ApiItemT]
):
    """Class describing UniFi number entity."""

    control_fn: Callable[[UnifiHub, str, float], Coroutine[Any, Any, Any]]
    value_fn: Callable[[UnifiHub, ApiItemT], float | None]


ENTITY_DESCRIPTIONS: tuple[UnifiNumberEntityDescription, ...] = (
    UnifiNumberEntityDescription[Networks, Network](
        key="WAN failover priority",
        translation_key="wan_failover_priority",
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_min_value=1,
        native_max_value=MAX_FAILOVER_PRIORITY,
        native_step=1,
        api_handler_fn=lambda api: api.networks,
        control_fn=lambda hub, obj_id, value: hub.api.networks.save(
            hub.api.networks[obj_id], wan_failover_priority=int(value)
        ),
        device_info_fn=async_wan_device_info_fn,
        object_fn=lambda api, obj_id: api.networks[obj_id],
        supported_fn=wan_supported_fn(lambda network: network.wan_failover_priority),
        unique_id_fn=lambda hub, obj_id: f"wan_failover_priority-{obj_id}",
        value_fn=lambda hub, network: network.wan_failover_priority,
    ),
    UnifiNumberEntityDescription[Networks, Network](
        key="WAN load balance weight",
        translation_key="wan_load_balance_weight",
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
        native_min_value=1,
        native_max_value=MAX_LOAD_BALANCE_WEIGHT,
        native_step=1,
        api_handler_fn=lambda api: api.networks,
        control_fn=lambda hub, obj_id, value: hub.api.networks.save(
            hub.api.networks[obj_id], wan_load_balance_weight=int(value)
        ),
        device_info_fn=async_wan_device_info_fn,
        object_fn=lambda api, obj_id: api.networks[obj_id],
        supported_fn=wan_supported_fn(lambda network: network.wan_load_balance_weight),
        unique_id_fn=lambda hub, obj_id: f"wan_load_balance_weight-{obj_id}",
        value_fn=lambda hub, network: network.wan_load_balance_weight,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UnifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up numbers for UniFi Network integration."""
    config_entry.runtime_data.entity_loader.register_platform(
        async_add_entities,
        UnifiNumberEntity,
        ENTITY_DESCRIPTIONS,
        requires_admin=True,
    )


class UnifiNumberEntity[HandlerT: APIHandler, ApiItemT: ApiItem](
    UnifiEntity[HandlerT, ApiItemT], NumberEntity
):
    """Base representation of a UniFi number entity."""

    entity_description: UnifiNumberEntityDescription[HandlerT, ApiItemT]

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set a new value."""
        await self.async_control(
            self.entity_description.control_fn(self.hub, self._obj_id, value)
        )

    @callback
    @override
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state.

        Update attr_native_value.
        """
        description = self.entity_description
        self._attr_native_value = description.value_fn(self.hub, self.get_object())

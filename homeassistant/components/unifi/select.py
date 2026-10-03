"""Select platform for UniFi Network integration.

Support for controlling the load balancing mode of WAN networks.
"""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, cast, override

import aiounifi
from aiounifi.interfaces.api_handlers import APIHandler, ItemEvent
from aiounifi.interfaces.networks import Networks
from aiounifi.models.api import ApiItem
from aiounifi.models.network import Network, WanLoadBalanceType

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UnifiConfigEntry
from .const import DOMAIN
from .entity import (
    UnifiEntity,
    UnifiEntityDescription,
    async_wan_device_info_fn,
    wan_supported_fn,
)
from .errors import controller_error_reason
from .hub import UnifiHub

PARALLEL_UPDATES = 1

# The controller requires at least one WAN to stay in the weighted load balance group.
ERROR_MISSING_WEIGHTED_WAN = "api.err.MissingWeightedWanNetwork"


async def async_wan_load_balance_type_control_fn(
    hub: UnifiHub, obj_id: str, option: str
) -> None:
    """Control load balance type of WAN network."""
    try:
        await hub.api.networks.save(
            hub.api.networks[obj_id],
            wan_load_balance_type=cast(WanLoadBalanceType, option),
        )
    except aiounifi.AiounifiException as err:
        if controller_error_reason(err) == ERROR_MISSING_WEIGHTED_WAN:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="wan_load_balance_weighted_required",
            ) from err
        raise


@dataclass(frozen=True, kw_only=True)
class UnifiSelectEntityDescription[HandlerT: APIHandler, ApiItemT: ApiItem](
    SelectEntityDescription, UnifiEntityDescription[HandlerT, ApiItemT]
):
    """Class describing UniFi select entity."""

    control_fn: Callable[[UnifiHub, str, str], Coroutine[Any, Any, None]]
    current_option_fn: Callable[[UnifiHub, ApiItemT], str | None]


ENTITY_DESCRIPTIONS: tuple[UnifiSelectEntityDescription, ...] = (
    UnifiSelectEntityDescription[Networks, Network](
        key="WAN load balancing",
        translation_key="wan_load_balancing",
        entity_category=EntityCategory.CONFIG,
        # Load balance type is group membership, the failover priority still decides
        # which WAN is active, so a weighted WAN is the primary while it is the only
        # member online.
        options=["failover-only", "weighted"],
        api_handler_fn=lambda api: api.networks,
        control_fn=async_wan_load_balance_type_control_fn,
        current_option_fn=lambda hub, network: network.wan_load_balance_type,
        device_info_fn=async_wan_device_info_fn,
        object_fn=lambda api, obj_id: api.networks[obj_id],
        supported_fn=wan_supported_fn(lambda network: network.wan_load_balance_type),
        unique_id_fn=lambda hub, obj_id: f"wan_load_balancing-{obj_id}",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: UnifiConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up selects for UniFi Network integration."""
    config_entry.runtime_data.entity_loader.register_platform(
        async_add_entities,
        UnifiSelectEntity,
        ENTITY_DESCRIPTIONS,
        requires_admin=True,
    )


class UnifiSelectEntity[HandlerT: APIHandler, ApiItemT: ApiItem](
    UnifiEntity[HandlerT, ApiItemT], SelectEntity
):
    """Base representation of a UniFi select entity."""

    entity_description: UnifiSelectEntityDescription[HandlerT, ApiItemT]

    @override
    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        await self.async_control(
            self.entity_description.control_fn(self.hub, self._obj_id, option)
        )

    @callback
    @override
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state.

        Update attr_current_option.
        """
        description = self.entity_description
        self._attr_current_option = description.current_option_fn(
            self.hub, self.get_object()
        )

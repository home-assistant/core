"""Switch platform for UniFi Network integration.

Support for controlling power supply of clients which are powered over Ethernet (POE).
Support for controlling network access of clients selected in option flow.
Support for controlling deep packet inspection (DPI) restriction groups.
Support for controlling WLAN availability.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic

import aiounifi
from aiounifi.interfaces.api_handlers import ItemEvent
from aiounifi.interfaces.clients import Clients
from aiounifi.interfaces.dpi_restriction_groups import DPIRestrictionGroups
from aiounifi.interfaces.outlets import Outlets
from aiounifi.interfaces.port_forwarding import PortForwarding
from aiounifi.interfaces.ports import Ports
from aiounifi.interfaces.wlans import Wlans
from aiounifi.models.api import ApiItemT
from aiounifi.models.client import Client, ClientBlockRequest
from aiounifi.models.device import DeviceSetOutletRelayRequest
from aiounifi.models.dpi_restriction_app import DPIRestrictionAppEnableRequest
from aiounifi.models.dpi_restriction_group import DPIRestrictionGroup
from aiounifi.models.event import Event, EventKey
from aiounifi.models.outlet import Outlet
from aiounifi.models.port import Port
from aiounifi.models.port_forward import PortForward, PortForwardEnableRequest
from aiounifi.models.wlan import Wlan, WlanEnableRequest

from homeassistant.components.switch import (
    DOMAIN,
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.entity_registry as er

from .const import ATTR_MANUFACTURER
from .controller import UNIFI_DOMAIN, UniFiController
from .entity import (
    HandlerT,
    SubscriptionT,
    UnifiEntity,
    UnifiEntityDescription,
    async_client_device_info_fn,
    async_device_available_fn,
    async_device_device_info_fn,
    async_wlan_device_info_fn,
)

CLIENT_BLOCKED = (EventKey.WIRED_CLIENT_BLOCKED, EventKey.WIRELESS_CLIENT_BLOCKED)
CLIENT_UNBLOCKED = (EventKey.WIRED_CLIENT_UNBLOCKED, EventKey.WIRELESS_CLIENT_UNBLOCKED)


@callback
def async_block_client_allowed_fn(controller: UniFiController, obj_id: str) -> bool:
    """Check if client is allowed."""
    if obj_id in controller.option_supported_clients:
        return True
    return obj_id in controller.option_block_clients


@callback
def async_dpi_group_is_on_fn(
    controller: UniFiController, dpi_group: DPIRestrictionGroup
) -> bool:
    """Calculate if all apps are enabled."""
    api = controller.api
    return all(
        api.dpi_apps[app_id].enabled
        for app_id in dpi_group.dpiapp_ids or []
        if app_id in api.dpi_apps
    )


@callback
def async_dpi_group_device_info_fn(
    controller: UniFiController, obj_id: str
) -> DeviceInfo:
    """Create device registry entry for DPI group."""
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, f"unifi_controller_{obj_id}")},
        manufacturer=ATTR_MANUFACTURER,
        model="UniFi Network",
        name="UniFi Network",
    )


@callback
def async_port_forward_device_info_fn(
    controller: UniFiController, obj_id: str
) -> DeviceInfo:
    """Create device registry entry for port forward."""
    unique_id = controller.config_entry.unique_id
    assert unique_id is not None
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, unique_id)},
        manufacturer=ATTR_MANUFACTURER,
        model="UniFi Network",
        name="UniFi Network",
    )


async def async_block_client_control_fn(
    controller: UniFiController, obj_id: str, target: bool
) -> None:
    """Control network access of client."""
    await controller.api.request(ClientBlockRequest.create(obj_id, not target))


async def async_dpi_group_control_fn(
    controller: UniFiController, obj_id: str, target: bool
) -> None:
    """Enable or disable DPI group."""
    dpi_group = controller.api.dpi_groups[obj_id]
    await asyncio.gather(
        *[
            controller.api.request(
                DPIRestrictionAppEnableRequest.create(app_id, target)
            )
            for app_id in dpi_group.dpiapp_ids or []
        ]
    )


@callback
def async_outlet_supports_switching_fn(
    controller: UniFiController, obj_id: str
) -> bool:
    """Determine if an outlet supports switching."""
    outlet = controller.api.outlets[obj_id]
    return outlet.has_relay or outlet.caps in (1, 3)


async def async_outlet_control_fn(
    controller: UniFiController, obj_id: str, target: bool
) -> None:
    """Control outlet relay."""
    mac, _, index = obj_id.partition("_")
    device = controller.api.devices[mac]
    await controller.api.request(
        DeviceSetOutletRelayRequest.create(device, int(index), target)
    )


async def async_poe_port_control_fn(
    controller: UniFiController, obj_id: str, target: bool
) -> None:
    """Control poe state."""
    mac, _, index = obj_id.partition("_")
    port = controller.api.ports[obj_id]
    on_state = "auto" if port.raw["poe_caps"] != 8 else "passthrough"
    state = on_state if target else "off"
    controller.async_queue_poe_port_command(mac, int(index), state)


async def async_port_forward_control_fn(
    controller: UniFiController, obj_id: str, target: bool
) -> None:
    """Control port forward state."""
    port_forward = controller.api.port_forwarding[obj_id]
    await controller.api.request(PortForwardEnableRequest.create(port_forward, target))


async def async_wlan_control_fn(
    controller: UniFiController, obj_id: str, target: bool
) -> None:
    """Control outlet relay."""
    await controller.api.request(WlanEnableRequest.create(obj_id, target))


@dataclass(frozen=True)
class UnifiSwitchEntityDescriptionMixin(Generic[HandlerT, ApiItemT]):
    """Validate and load entities from different UniFi handlers."""

    control_fn: Callable[[UniFiController, str, bool], Coroutine[Any, Any, None]]
    is_on_fn: Callable[[UniFiController, ApiItemT], bool]


@dataclass(frozen=True)
class UnifiSwitchEntityDescription(
    SwitchEntityDescription,
    UnifiEntityDescription[HandlerT, ApiItemT],
    UnifiSwitchEntityDescriptionMixin[HandlerT, ApiItemT],
):
    """Class describing UniFi switch entity."""

    custom_subscribe: Callable[[aiounifi.Controller], SubscriptionT] | None = None
    only_event_for_state_change: bool = False


ENTITY_DESCRIPTIONS: tuple[UnifiSwitchEntityDescription, ...] = (
    UnifiSwitchEntityDescription[Clients, Client](
        key="Block client",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
        icon="mdi:ethernet",
        allowed_fn=async_block_client_allowed_fn,
        api_handler_fn=lambda api: api.clients,
        available_fn=lambda controller, obj_id: controller.available,
        control_fn=async_block_client_control_fn,
        device_info_fn=async_client_device_info_fn,
        event_is_on=CLIENT_UNBLOCKED,
        event_to_subscribe=CLIENT_BLOCKED + CLIENT_UNBLOCKED,
        is_on_fn=lambda controller, client: not client.blocked,
        name_fn=lambda client: None,
        object_fn=lambda api, obj_id: api.clients[obj_id],
        only_event_for_state_change=True,
        should_poll=False,
        supported_fn=lambda controller, obj_id: True,
        unique_id_fn=lambda controller, obj_id: f"block-{obj_id}",
    ),
    UnifiSwitchEntityDescription[DPIRestrictionGroups, DPIRestrictionGroup](
        key="DPI restriction",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:network",
        allowed_fn=lambda controller, obj_id: controller.option_dpi_restrictions,
        api_handler_fn=lambda api: api.dpi_groups,
        available_fn=lambda controller, obj_id: controller.available,
        control_fn=async_dpi_group_control_fn,
        custom_subscribe=lambda api: api.dpi_apps.subscribe,
        device_info_fn=async_dpi_group_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        is_on_fn=async_dpi_group_is_on_fn,
        name_fn=lambda group: group.name,
        object_fn=lambda api, obj_id: api.dpi_groups[obj_id],
        should_poll=False,
        supported_fn=lambda c, obj_id: bool(c.api.dpi_groups[obj_id].dpiapp_ids),
        unique_id_fn=lambda controller, obj_id: obj_id,
    ),
    UnifiSwitchEntityDescription[Outlets, Outlet](
        key="Outlet control",
        device_class=SwitchDeviceClass.OUTLET,
        has_entity_name=True,
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.outlets,
        available_fn=async_device_available_fn,
        control_fn=async_outlet_control_fn,
        device_info_fn=async_device_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        is_on_fn=lambda controller, outlet: outlet.relay_state,
        name_fn=lambda outlet: outlet.name,
        object_fn=lambda api, obj_id: api.outlets[obj_id],
        should_poll=False,
        supported_fn=async_outlet_supports_switching_fn,
        unique_id_fn=lambda controller, obj_id: f"outlet-{obj_id}",
    ),
    UnifiSwitchEntityDescription[PortForwarding, PortForward](
        key="Port forward control",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
        icon="mdi:upload-network",
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.port_forwarding,
        available_fn=lambda controller, obj_id: controller.available,
        control_fn=async_port_forward_control_fn,
        device_info_fn=async_port_forward_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        is_on_fn=lambda controller, port_forward: port_forward.enabled,
        name_fn=lambda port_forward: f"{port_forward.name}",
        object_fn=lambda api, obj_id: api.port_forwarding[obj_id],
        should_poll=False,
        supported_fn=lambda controller, obj_id: True,
        unique_id_fn=lambda controller, obj_id: f"port_forward-{obj_id}",
    ),
    UnifiSwitchEntityDescription[Ports, Port](
        key="PoE port control",
        device_class=SwitchDeviceClass.OUTLET,
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
        entity_registry_enabled_default=False,
        icon="mdi:ethernet",
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.ports,
        available_fn=async_device_available_fn,
        control_fn=async_poe_port_control_fn,
        device_info_fn=async_device_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        is_on_fn=lambda controller, port: port.poe_mode != "off",
        name_fn=lambda port: f"{port.name} PoE",
        object_fn=lambda api, obj_id: api.ports[obj_id],
        should_poll=False,
        supported_fn=lambda controller, obj_id: controller.api.ports[obj_id].port_poe,
        unique_id_fn=lambda controller, obj_id: f"poe-{obj_id}",
    ),
    UnifiSwitchEntityDescription[Wlans, Wlan](
        key="WLAN control",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
        icon="mdi:wifi-check",
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.wlans,
        available_fn=lambda controller, _: controller.available,
        control_fn=async_wlan_control_fn,
        device_info_fn=async_wlan_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        is_on_fn=lambda controller, wlan: wlan.enabled,
        name_fn=lambda wlan: None,
        object_fn=lambda api, obj_id: api.wlans[obj_id],
        should_poll=False,
        supported_fn=lambda controller, obj_id: True,
        unique_id_fn=lambda controller, obj_id: f"wlan-{obj_id}",
    ),
)


@callback
def async_update_unique_id(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Normalize switch unique ID to have a prefix rather than midfix.

    Introduced with release 2023.12.
    """
    controller: UniFiController = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    ent_reg = er.async_get(hass)

    @callback
    def update_unique_id(obj_id: str, type_name: str) -> None:
        """Rework unique ID."""
        new_unique_id = f"{type_name}-{obj_id}"
        if ent_reg.async_get_entity_id(DOMAIN, UNIFI_DOMAIN, new_unique_id):
            return

        prefix, _, suffix = obj_id.partition("_")
        unique_id = f"{prefix}-{type_name}-{suffix}"
        if entity_id := ent_reg.async_get_entity_id(DOMAIN, UNIFI_DOMAIN, unique_id):
            ent_reg.async_update_entity(entity_id, new_unique_id=new_unique_id)

    for obj_id in controller.api.outlets:
        update_unique_id(obj_id, "outlet")

    for obj_id in controller.api.ports:
        update_unique_id(obj_id, "poe")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for UniFi Network integration."""
    async_update_unique_id(hass, config_entry)
    UniFiController.register_platform(
        hass,
        config_entry,
        async_add_entities,
        UnifiSwitchEntity,
        ENTITY_DESCRIPTIONS,
        requires_admin=True,
    )


class UnifiSwitchEntity(UnifiEntity[HandlerT, ApiItemT], SwitchEntity):
    """Base representation of a UniFi switch."""

    entity_description: UnifiSwitchEntityDescription[HandlerT, ApiItemT]
    only_event_for_state_change = False

    @callback
    def async_initiate_state(self) -> None:
        """Initiate entity state."""
        self.async_update_state(ItemEvent.ADDED, self._obj_id)
        self.only_event_for_state_change = (
            self.entity_description.only_event_for_state_change
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self.entity_description.control_fn(self.controller, self._obj_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self.entity_description.control_fn(self.controller, self._obj_id, False)

    @callback
    def async_update_state(self, event: ItemEvent, obj_id: str) -> None:
        """Update entity state.

        Update attr_is_on.
        """
        if self.only_event_for_state_change:
            return

        description = self.entity_description
        obj = description.object_fn(self.controller.api, self._obj_id)
        if (is_on := description.is_on_fn(self.controller, obj)) != self.is_on:
            self._attr_is_on = is_on

    @callback
    def async_event_callback(self, event: Event) -> None:
        """Event subscription callback."""
        if event.mac != self._obj_id:
            return

        description = self.entity_description
        assert isinstance(description.event_to_subscribe, tuple)
        assert isinstance(description.event_is_on, tuple)

        if event.key in description.event_to_subscribe:
            self._attr_is_on = event.key in description.event_is_on
        self._attr_available = description.available_fn(self.controller, self._obj_id)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        if self.entity_description.custom_subscribe is not None:
            self.async_on_remove(
                self.entity_description.custom_subscribe(self.controller.api)(
                    self.async_signalling_callback, ItemEvent.CHANGED
                ),
            )

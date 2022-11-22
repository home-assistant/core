"""Switch platform for UniFi Network integration.

Support for controlling power supply of clients which are powered over Ethernet (POE).
Support for controlling network access of clients selected in option flow.
Support for controlling deep packet inspection (DPI) restriction groups.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

import aiounifi
from aiounifi.interfaces.api_handlers import CallbackType, ItemEvent, UnsubscribeType
from aiounifi.interfaces.clients import Clients
from aiounifi.interfaces.dpi_restriction_groups import DPIRestrictionGroups
from aiounifi.interfaces.outlets import Outlets
from aiounifi.interfaces.ports import Ports
from aiounifi.models.client import Client, ClientBlockRequest
from aiounifi.models.device import (
    DeviceSetOutletRelayRequest,
    DeviceSetPoePortModeRequest,
)
from aiounifi.models.dpi_restriction_app import DPIRestrictionAppEnableRequest
from aiounifi.models.dpi_restriction_group import DPIRestrictionGroup
from aiounifi.models.event import Event, EventKey
from aiounifi.models.outlet import Outlet
from aiounifi.models.port import Port

from homeassistant.components.switch import (
    DOMAIN,
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceEntryType,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_MANUFACTURER, DOMAIN as UNIFI_DOMAIN
from .controller import UniFiController

CLIENT_BLOCKED = (EventKey.WIRED_CLIENT_BLOCKED, EventKey.WIRELESS_CLIENT_BLOCKED)
CLIENT_UNBLOCKED = (EventKey.WIRED_CLIENT_UNBLOCKED, EventKey.WIRELESS_CLIENT_UNBLOCKED)

Data = TypeVar("Data")
Handler = TypeVar("Handler")

Subscription = Callable[[CallbackType, ItemEvent], UnsubscribeType]


@callback
def async_dpi_group_is_on_fn(
    api: aiounifi.Controller, dpi_group: DPIRestrictionGroup
) -> bool:
    """Calculate if all apps are enabled."""
    return all(
        api.dpi_apps[app_id].enabled
        for app_id in dpi_group.dpiapp_ids or []
        if app_id in api.dpi_apps
    )


@callback
def async_sub_device_available_fn(controller: UniFiController, obj_id: str) -> bool:
    """Check if sub device object is disabled."""
    device_id = obj_id.partition("_")[0]
    device = controller.api.devices[device_id]
    return controller.available and not device.disabled


@callback
def async_client_device_info_fn(api: aiounifi.Controller, obj_id: str) -> DeviceInfo:
    """Create device registry entry for client."""
    client = api.clients[obj_id]
    return DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, obj_id)},
        default_manufacturer=client.oui,
        default_name=client.name or client.hostname,
    )


@callback
def async_device_device_info_fn(api: aiounifi.Controller, obj_id: str) -> DeviceInfo:
    """Create device registry entry for device."""
    if "_" in obj_id:  # Sub device
        obj_id = obj_id.partition("_")[0]

    device = api.devices[obj_id]
    return DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, device.mac)},
        manufacturer=ATTR_MANUFACTURER,
        model=device.model,
        name=device.name or None,
        sw_version=device.version,
        hw_version=str(device.board_revision),
    )


@callback
def async_dpi_group_device_info_fn(api: aiounifi.Controller, obj_id: str) -> DeviceInfo:
    """Create device registry entry for DPI group."""
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, f"unifi_controller_{obj_id}")},
        manufacturer=ATTR_MANUFACTURER,
        model="UniFi Network",
        name="UniFi Network",
    )


async def async_block_client_control_fn(
    api: aiounifi.Controller, obj_id: str, target: bool
) -> None:
    """Control network access of client."""
    await api.request(ClientBlockRequest.create(obj_id, not target))


async def async_dpi_group_control_fn(
    api: aiounifi.Controller, obj_id: str, target: bool
) -> None:
    """Enable or disable DPI group."""
    dpi_group = api.dpi_groups[obj_id]
    await asyncio.gather(
        *[
            api.request(DPIRestrictionAppEnableRequest.create(app_id, target))
            for app_id in dpi_group.dpiapp_ids or []
        ]
    )


async def async_outlet_control_fn(
    api: aiounifi.Controller, obj_id: str, target: bool
) -> None:
    """Control outlet relay."""
    mac, _, index = obj_id.partition("_")
    device = api.devices[mac]
    await api.request(DeviceSetOutletRelayRequest.create(device, int(index), target))


async def async_poe_port_control_fn(
    api: aiounifi.Controller, obj_id: str, target: bool
) -> None:
    """Control poe state."""
    mac, _, index = obj_id.partition("_")
    device = api.devices[mac]
    state = "auto" if target else "off"
    await api.request(DeviceSetPoePortModeRequest.create(device, int(index), state))


@dataclass
class UnifiEntityLoader(Generic[Handler, Data]):
    """Validate and load entities from different UniFi handlers."""

    allowed_fn: Callable[[UniFiController, str], bool]
    api_handler_fn: Callable[[aiounifi.Controller], Handler]
    available_fn: Callable[[UniFiController, str], bool]
    control_fn: Callable[[aiounifi.Controller, str, bool], Coroutine[Any, Any, None]]
    device_info_fn: Callable[[aiounifi.Controller, str], DeviceInfo]
    event_is_on: tuple[EventKey, ...] | None
    event_to_subscribe: tuple[EventKey, ...] | None
    is_on_fn: Callable[[aiounifi.Controller, Data], bool]
    name_fn: Callable[[Data], str | None]
    object_fn: Callable[[aiounifi.Controller, str], Data]
    supported_fn: Callable[[aiounifi.Controller, str], bool | None]
    unique_id_fn: Callable[[str], str]


@dataclass
class UnifiEntityDescription(SwitchEntityDescription, UnifiEntityLoader[Handler, Data]):
    """Class describing UniFi switch entity."""

    custom_subscribe: Callable[[aiounifi.Controller], Subscription] | None = None
    only_event_for_state_change: bool = False


ENTITY_DESCRIPTIONS: tuple[UnifiEntityDescription, ...] = (
    UnifiEntityDescription[Clients, Client](
        key="Block client",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
        icon="mdi:ethernet",
        allowed_fn=lambda controller, obj_id: obj_id in controller.option_block_clients,
        api_handler_fn=lambda api: api.clients,
        available_fn=lambda controller, obj_id: controller.available,
        control_fn=async_block_client_control_fn,
        device_info_fn=async_client_device_info_fn,
        event_is_on=CLIENT_UNBLOCKED,
        event_to_subscribe=CLIENT_BLOCKED + CLIENT_UNBLOCKED,
        is_on_fn=lambda api, client: not client.blocked,
        name_fn=lambda client: None,
        object_fn=lambda api, obj_id: api.clients[obj_id],
        only_event_for_state_change=True,
        supported_fn=lambda api, obj_id: True,
        unique_id_fn=lambda obj_id: f"block-{obj_id}",
    ),
    UnifiEntityDescription[DPIRestrictionGroups, DPIRestrictionGroup](
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
        supported_fn=lambda api, obj_id: bool(api.dpi_groups[obj_id].dpiapp_ids),
        unique_id_fn=lambda obj_id: obj_id,
    ),
    UnifiEntityDescription[Outlets, Outlet](
        key="Outlet control",
        device_class=SwitchDeviceClass.OUTLET,
        has_entity_name=True,
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.outlets,
        available_fn=async_sub_device_available_fn,
        control_fn=async_outlet_control_fn,
        device_info_fn=async_device_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        is_on_fn=lambda api, outlet: outlet.relay_state,
        name_fn=lambda outlet: outlet.name,
        object_fn=lambda api, obj_id: api.outlets[obj_id],
        supported_fn=lambda api, obj_id: api.outlets[obj_id].has_relay,
        unique_id_fn=lambda obj_id: f"{obj_id.split('_', 1)[0]}-outlet-{obj_id.split('_', 1)[1]}",
    ),
    UnifiEntityDescription[Ports, Port](
        key="PoE port control",
        device_class=SwitchDeviceClass.OUTLET,
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
        entity_registry_enabled_default=False,
        icon="mdi:ethernet",
        allowed_fn=lambda controller, obj_id: True,
        api_handler_fn=lambda api: api.ports,
        available_fn=async_sub_device_available_fn,
        control_fn=async_poe_port_control_fn,
        device_info_fn=async_device_device_info_fn,
        event_is_on=None,
        event_to_subscribe=None,
        is_on_fn=lambda api, port: port.poe_mode != "off",
        name_fn=lambda port: f"{port.name} PoE",
        object_fn=lambda api, obj_id: api.ports[obj_id],
        supported_fn=lambda api, obj_id: api.ports[obj_id].port_poe,
        unique_id_fn=lambda obj_id: f"{obj_id.split('_', 1)[0]}-poe-{obj_id.split('_', 1)[1]}",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for UniFi Network integration."""
    controller: UniFiController = hass.data[UNIFI_DOMAIN][config_entry.entry_id]

    if controller.site_role != "admin":
        return

    for mac in controller.option_block_clients:
        if mac not in controller.api.clients and mac in controller.api.clients_all:
            client = controller.api.clients_all[mac]
            controller.api.clients.process_raw([client.raw])

    @callback
    def async_load_entities(description: UnifiEntityDescription) -> None:
        """Load and subscribe to UniFi devices."""
        entities: list[SwitchEntity] = []
        api_handler = description.api_handler_fn(controller.api)

        @callback
        def async_create_entity(event: ItemEvent, obj_id: str) -> None:
            """Create UniFi entity."""
            if not description.allowed_fn(
                controller, obj_id
            ) or not description.supported_fn(controller.api, obj_id):
                return

            entity = UnifiSwitchEntity(obj_id, controller, description)
            if event == ItemEvent.ADDED:
                async_add_entities([entity])
                return
            entities.append(entity)

        for obj_id in api_handler:
            async_create_entity(ItemEvent.CHANGED, obj_id)
        async_add_entities(entities)

        api_handler.subscribe(async_create_entity, ItemEvent.ADDED)

    for description in ENTITY_DESCRIPTIONS:
        async_load_entities(description)


class UnifiSwitchEntity(SwitchEntity):
    """Base representation of a UniFi switch."""

    entity_description: UnifiEntityDescription
    _attr_should_poll = False

    def __init__(
        self,
        obj_id: str,
        controller: UniFiController,
        description: UnifiEntityDescription,
    ) -> None:
        """Set up UniFi switch entity."""
        self._obj_id = obj_id
        self.controller = controller
        self.entity_description = description

        self._removed = False

        self._attr_available = description.available_fn(controller, obj_id)
        self._attr_device_info = description.device_info_fn(controller.api, obj_id)
        self._attr_unique_id = description.unique_id_fn(obj_id)

        obj = description.object_fn(self.controller.api, obj_id)
        self._attr_is_on = description.is_on_fn(controller.api, obj)
        self._attr_name = description.name_fn(obj)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self.entity_description.control_fn(
            self.controller.api, self._obj_id, True
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self.entity_description.control_fn(
            self.controller.api, self._obj_id, False
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        description = self.entity_description
        handler = description.api_handler_fn(self.controller.api)
        self.async_on_remove(
            handler.subscribe(
                self.async_signalling_callback,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.controller.signal_reachable,
                self.async_signal_reachable_callback,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.controller.signal_options_update,
                self.options_updated,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.controller.signal_remove,
                self.remove_item,
            )
        )
        if description.event_to_subscribe is not None:
            self.async_on_remove(
                self.controller.api.events.subscribe(
                    self.async_event_callback,
                    description.event_to_subscribe,
                )
            )
        if description.custom_subscribe is not None:
            self.async_on_remove(
                description.custom_subscribe(self.controller.api)(
                    self.async_signalling_callback, ItemEvent.CHANGED
                ),
            )

    @callback
    def async_signalling_callback(self, event: ItemEvent, obj_id: str) -> None:
        """Update the switch state."""
        if event == ItemEvent.DELETED and obj_id == self._obj_id:
            self.hass.async_create_task(self.remove_item({self._obj_id}))
            return

        description = self.entity_description
        if not description.supported_fn(self.controller.api, self._obj_id):
            self.hass.async_create_task(self.remove_item({self._obj_id}))
            return

        if not description.only_event_for_state_change:
            obj = description.object_fn(self.controller.api, self._obj_id)
            self._attr_is_on = description.is_on_fn(self.controller.api, obj)
        self._attr_available = description.available_fn(self.controller, self._obj_id)
        self.async_write_ha_state()

    @callback
    def async_signal_reachable_callback(self) -> None:
        """Call when controller connection state change."""
        self.async_signalling_callback(ItemEvent.ADDED, self._obj_id)

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

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.entity_description.allowed_fn(self.controller, self._obj_id):
            await self.remove_item({self._obj_id})

    async def remove_item(self, keys: set) -> None:
        """Remove entity if object ID is part of set."""
        if self._obj_id not in keys or self._removed:
            return
        self._removed = True
        if self.registry_entry:
            er.async_get(self.hass).async_remove(self.entity_id)
        else:
            await self.async_remove(force_remove=True)

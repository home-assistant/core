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

from aiounifi.interfaces.api_handlers import ItemEvent
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
from homeassistant.helpers.restore_state import RestoreEntity

from .const import ATTR_MANUFACTURER, DOMAIN as UNIFI_DOMAIN, POE_SWITCH
from .controller import UniFiController
from .unifi_client import UniFiClient

CLIENT_BLOCKED = (EventKey.WIRED_CLIENT_BLOCKED, EventKey.WIRELESS_CLIENT_BLOCKED)
CLIENT_UNBLOCKED = (EventKey.WIRED_CLIENT_UNBLOCKED, EventKey.WIRELESS_CLIENT_UNBLOCKED)

T = TypeVar("T")
V = TypeVar("V")


@dataclass
class UnifiEntityLoader(Generic[T, V]):
    """Validate and load entities from different UniFi handlers."""

    allowed_fn: Callable[[UniFiController, str], bool]
    available_fn: Callable[[UniFiController, str], bool]
    control_fn: Callable[[UniFiController, str, bool], Coroutine[Any, Any, None]]
    device_info: Callable[[UniFiController, str], DeviceInfo]
    entity_cls: type[UnifiSwitchEntity] | type[UnifiDPIRestrictionSwitch]
    event_is_on: tuple[EventKey, ...] | None
    event_to_subscribe: tuple[EventKey, ...] | None
    handler_fn: Callable[[UniFiController], T]
    is_on_fn: Callable[[UniFiController, V], bool]
    name_fn: Callable[[V], str | None]
    object_fn: Callable[[T, str], V]
    supported_fn: Callable[[T, str], bool | None]
    unique_id_fn: Callable[[str], str]


@dataclass
class UnifiEntityDescription(SwitchEntityDescription, UnifiEntityLoader[T, V]):
    """Class describing UniFi switch entity."""


def calculate_enabled_dpi_apps(
    controller: UniFiController, dpi_group: DPIRestrictionGroup
) -> bool:
    """Calculate if all apps are enabled."""
    dpi_apps = controller.api.dpi_apps
    return all(
        dpi_apps[app_id].enabled
        for app_id in dpi_group.dpiapp_ids or []
        if app_id in dpi_apps
    )


def sub_device_disabled(controller: UniFiController, obj_id: str) -> bool:
    """Check if sub device object is disabled."""
    device_id = obj_id.split("_", 1)[0]
    device = controller.api.devices[device_id]
    return controller.available and not device.disabled


def client_registry_entry(controller: UniFiController, obj_id: str) -> DeviceInfo:
    """Create device registry entry for client."""
    client = controller.api.clients[obj_id]
    return DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, obj_id)},
        default_manufacturer=client.oui,
        default_name=client.name or client.hostname,
    )


def device_registry_entry(controller: UniFiController, obj_id: str) -> DeviceInfo:
    """Create device registry entry for device."""
    if "_" in obj_id:  # Sub device
        obj_id = obj_id.split("_", 1)[0]

    device = controller.api.devices[obj_id]
    return DeviceInfo(
        connections={(CONNECTION_NETWORK_MAC, device.mac)},
        manufacturer=ATTR_MANUFACTURER,
        model=device.model,
        name=device.name or None,
        sw_version=device.version,
        hw_version=device.board_revision,
    )


def dpi_group_registry_entry(controller: UniFiController, obj_id: str) -> DeviceInfo:
    """Create device registry entry for DPI group."""
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, f"unifi_controller_{obj_id}")},
        manufacturer=ATTR_MANUFACTURER,
        model="UniFi Network",
        name="UniFi Network",
    )


async def async_control_block_client(
    controller: UniFiController, obj_id: str, target: bool
) -> None:
    """Control network access of client."""
    await controller.api.request(ClientBlockRequest.create(obj_id, not target))


async def async_control_dpi_group(
    controller: UniFiController, obj_id: str, target: bool
) -> None:
    """Enable or disable DPI group."""
    dpi_group = controller.api.dpi_groups[obj_id]
    await asyncio.gather(
        *[
            controller.api.request(
                DPIRestrictionAppEnableRequest.create(app_id, target)
            )
            for app_id in dpi_group.dpiapp_ids
        ]
    )


async def async_control_outlet(
    controller: UniFiController, obj_id: str, target: bool
) -> None:
    """Control outlet relay."""
    mac, index = obj_id.split("_", 1)
    device = controller.api.devices[mac]
    await controller.api.request(
        DeviceSetOutletRelayRequest.create(device, int(index), target)
    )


async def async_control_poe_port(
    controller: UniFiController, obj_id: str, target: bool
) -> None:
    """Control poe state."""
    mac, index = obj_id.split("_", 1)
    device = controller.api.devices[mac]
    state = "auto" if target else "off"
    await controller.api.request(
        DeviceSetPoePortModeRequest.create(device, int(index), state)
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for UniFi Network integration."""
    controller: UniFiController = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    controller.entities[DOMAIN] = {POE_SWITCH: set()}

    if controller.site_role != "admin":
        return

    # Store previously known POE control entities in case their POE are turned off.
    known_poe_clients = []
    entity_registry = er.async_get(hass)
    for entry in er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    ):

        if not entry.unique_id.startswith(POE_SWITCH):
            continue

        mac = entry.unique_id.replace(f"{POE_SWITCH}-", "")
        if mac not in controller.api.clients:
            continue

        known_poe_clients.append(mac)

    for mac in controller.option_block_clients:
        if mac not in controller.api.clients and mac in controller.api.clients_all:
            client = controller.api.clients_all[mac]
            controller.api.clients.process_raw([client.raw])

    @callback
    def items_added(
        clients: set = controller.api.clients,
        devices: set = controller.api.devices,
    ) -> None:
        """Update the values of the controller."""
        if controller.option_poe_clients:
            add_poe_entities(controller, async_add_entities, clients, known_poe_clients)

    for signal in (controller.signal_update, controller.signal_options_update):
        config_entry.async_on_unload(
            async_dispatcher_connect(hass, signal, items_added)
        )

    items_added()
    known_poe_clients.clear()

    @callback
    def async_load_entities(loader: UnifiEntityDescription) -> None:
        """Load and subscribe to UniFi devices."""
        entities: list[SwitchEntity] = []
        api_handler = loader.handler_fn(controller)

        @callback
        def async_create_entity(event: ItemEvent, obj_id: str) -> None:
            """Create UniFi entity."""
            if not loader.allowed_fn(controller, obj_id) or not loader.supported_fn(
                api_handler, obj_id
            ):
                return

            entity = loader.entity_cls(obj_id, controller, loader)
            if event == ItemEvent.ADDED:
                async_add_entities([entity])
                return
            entities.append(entity)

        for obj_id in api_handler:
            async_create_entity(ItemEvent.CHANGED, obj_id)
        async_add_entities(entities)

        api_handler.subscribe(async_create_entity, ItemEvent.ADDED)

    for unifi_loader in UNIFI_LOADERS:
        async_load_entities(unifi_loader)


@callback
def add_poe_entities(controller, async_add_entities, clients, known_poe_clients):
    """Add new switch entities from the controller."""
    switches = []

    devices = controller.api.devices

    for mac in clients:
        if mac in controller.entities[DOMAIN][POE_SWITCH]:
            continue

        client = controller.api.clients[mac]

        # Try to identify new clients powered by POE.
        # Known POE clients have been created in previous HASS sessions.
        # If port_poe is None the port does not support POE
        # If poe_enable is False we can't know if a POE client is available for control.
        if mac not in known_poe_clients and (
            mac in controller.wireless_clients
            or client.switch_mac not in devices
            or not devices[client.switch_mac].ports[client.switch_port].port_poe
            or not devices[client.switch_mac].ports[client.switch_port].poe_enable
            or controller.mac == client.mac
        ):
            continue

        # Multiple POE-devices on same port means non UniFi POE driven switch
        multi_clients_on_port = False
        for client2 in controller.api.clients.values():

            if mac in known_poe_clients:
                break

            if (
                client2.is_wired
                and client.mac != client2.mac
                and client.switch_mac == client2.switch_mac
                and client.switch_port == client2.switch_port
            ):
                multi_clients_on_port = True
                break

        if multi_clients_on_port:
            continue

        switches.append(UniFiPOEClientSwitch(client, controller))

    async_add_entities(switches)


class UniFiPOEClientSwitch(UniFiClient, SwitchEntity, RestoreEntity):
    """Representation of a client that uses POE."""

    DOMAIN = DOMAIN
    TYPE = POE_SWITCH

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client, controller):
        """Set up POE switch."""
        super().__init__(client, controller)

        self.poe_mode = None
        if client.switch_port and self.port.poe_mode != "off":
            self.poe_mode = self.port.poe_mode

    async def async_added_to_hass(self) -> None:
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()

        if self.poe_mode:  # POE is enabled and client in a known state
            return

        if (state := await self.async_get_last_state()) is None:
            return

        self.poe_mode = state.attributes.get("poe_mode")

        if not self.client.switch_mac:
            self.client.raw["sw_mac"] = state.attributes.get("switch")

        if not self.client.switch_port:
            self.client.raw["sw_port"] = state.attributes.get("port")

    @property
    def is_on(self):
        """Return true if POE is active."""
        return self.port.poe_mode != "off"

    @property
    def available(self) -> bool:
        """Return if switch is available.

        Poe_mode None means its POE state is unknown.
        Sw_mac unavailable means restored client.
        """
        return (
            self.poe_mode is not None
            and self.controller.available
            and self.client.switch_port
            and self.client.switch_mac
            and self.client.switch_mac in self.controller.api.devices
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable POE for client."""
        await self.controller.api.request(
            DeviceSetPoePortModeRequest.create(
                self.device, self.client.switch_port, self.poe_mode
            )
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable POE for client."""
        await self.controller.api.request(
            DeviceSetPoePortModeRequest.create(
                self.device, self.client.switch_port, "off"
            )
        )

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        attributes = {
            "power": self.port.poe_power,
            "switch": self.client.switch_mac,
            "port": self.client.switch_port,
            "poe_mode": self.poe_mode,
        }
        return attributes

    @property
    def device(self):
        """Shortcut to the switch that client is connected to."""
        return self.controller.api.devices[self.client.switch_mac]

    @property
    def port(self):
        """Shortcut to the switch port that client is connected to."""
        return self.device.ports[self.client.switch_port]

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_poe_clients:
            await self.remove_item({self.client.mac})


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
        """Set up dpi switch."""
        self._obj_id = obj_id
        self.controller = controller
        self.entity_description = description

        self._removed = False

        self._attr_available = description.available_fn(controller, obj_id)
        self._attr_device_info = description.device_info(controller, obj_id)
        self._attr_unique_id = description.unique_id_fn(obj_id)

        self.handler = description.handler_fn(controller)
        obj = description.object_fn(self.handler, obj_id)
        self._attr_is_on = description.is_on_fn(controller, obj)
        self._attr_name = description.name_fn(obj)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on connectivity for client."""
        await self.entity_description.control_fn(self.controller, self._obj_id, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off connectivity for client."""
        await self.entity_description.control_fn(self.controller, self._obj_id, False)

    async def async_added_to_hass(self) -> None:
        """Register callback to known apps."""
        self.async_on_remove(
            self.handler.subscribe(
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
        if self.entity_description.event_to_subscribe is not None:
            self.async_on_remove(
                self.controller.api.events.subscribe(
                    self.async_event_callback,
                    self.entity_description.event_to_subscribe,
                )
            )

    @callback
    def async_signalling_callback(self, event: ItemEvent, obj_id: str) -> None:
        """Update the clients state."""
        if event == ItemEvent.DELETED:
            self.hass.async_create_task(self.remove_item({self._obj_id}))
            return

        obj = self.entity_description.object_fn(self.handler, self._obj_id)
        self._attr_is_on = self.entity_description.is_on_fn(self.controller, obj)
        self._attr_available = self.entity_description.available_fn(
            self.controller, self._obj_id
        )
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
        assert isinstance(self.entity_description.event_to_subscribe, tuple)
        assert isinstance(self.entity_description.event_is_on, tuple)
        if event.key in self.entity_description.event_to_subscribe:
            self._attr_is_on = event.key in self.entity_description.event_is_on
        self._attr_available = self.controller.available
        self.async_write_ha_state()

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.entity_description.allowed_fn(self.controller, self._obj_id):
            await self.remove_item({self._obj_id})

    async def remove_item(self, keys: set) -> None:
        """Remove entity if key is part of set."""
        if self._obj_id not in keys or self._removed:
            return
        self._removed = True
        if self.registry_entry:
            er.async_get(self.hass).async_remove(self.entity_id)
        else:
            await self.async_remove(force_remove=True)


class UnifiDPIRestrictionSwitch(UnifiSwitchEntity):
    """Representation of a DPI restriction group."""

    async def async_added_to_hass(self) -> None:
        """Register callback to known apps."""
        self.async_on_remove(
            self.controller.api.dpi_apps.subscribe(
                self.async_signalling_callback, ItemEvent.CHANGED
            ),
        )
        await super().async_added_to_hass()

    @callback
    def async_signalling_callback(self, event: ItemEvent, obj_id: str) -> None:
        """Object has new event."""
        if event == ItemEvent.DELETED:
            self.hass.async_create_task(self.remove_item({self._obj_id}))
            return

        dpi_group = self.controller.api.dpi_groups[self._obj_id]
        if not dpi_group.dpiapp_ids:
            self.hass.async_create_task(self.remove_item({self._obj_id}))
            return

        super().async_signalling_callback(event, self._obj_id)


UNIFI_LOADERS: tuple[UnifiEntityDescription, ...] = (
    UnifiEntityDescription[Clients, Client](
        key="Block client",
        device_class=SwitchDeviceClass.SWITCH,
        entity_category=EntityCategory.CONFIG,
        has_entity_name=True,
        icon="mdi:ethernet",
        allowed_fn=lambda controller, obj_id: obj_id in controller.option_block_clients,
        available_fn=lambda controller, obj_id: controller.available,
        control_fn=async_control_block_client,
        device_info=client_registry_entry,
        entity_cls=UnifiSwitchEntity,
        event_is_on=CLIENT_UNBLOCKED,
        event_to_subscribe=CLIENT_BLOCKED + CLIENT_UNBLOCKED,
        is_on_fn=lambda controller, client: not client.blocked,
        name_fn=lambda client: None,
        object_fn=lambda handler, obj_id: handler[obj_id],
        handler_fn=lambda contrlr: contrlr.api.clients,
        supported_fn=lambda handler, obj_id: True,
        unique_id_fn=lambda obj_id: f"block-{obj_id}",
    ),
    UnifiEntityDescription[DPIRestrictionGroups, DPIRestrictionGroup](
        key="DPI restriction",
        entity_category=EntityCategory.CONFIG,
        allowed_fn=lambda controller, obj_id: controller.option_dpi_restrictions,
        available_fn=lambda controller, obj_id: controller.available,
        control_fn=async_control_dpi_group,
        device_info=dpi_group_registry_entry,
        entity_cls=UnifiDPIRestrictionSwitch,
        event_is_on=None,
        event_to_subscribe=None,
        is_on_fn=calculate_enabled_dpi_apps,
        name_fn=lambda group: group.name,
        object_fn=lambda handler, obj_id: handler[obj_id],
        handler_fn=lambda controller: controller.api.dpi_groups,
        supported_fn=lambda handler, obj_id: bool(handler[obj_id].dpiapp_ids),
        unique_id_fn=lambda obj_id: obj_id,
    ),
    UnifiEntityDescription[Outlets, Outlet](
        key="Outlet control",
        device_class=SwitchDeviceClass.OUTLET,
        has_entity_name=True,
        allowed_fn=lambda controller, obj_id: True,
        available_fn=sub_device_disabled,
        control_fn=async_control_outlet,
        device_info=device_registry_entry,
        entity_cls=UnifiSwitchEntity,
        event_is_on=None,
        event_to_subscribe=None,
        is_on_fn=lambda controller, outlet: outlet.relay_state,
        name_fn=lambda outlet: outlet.name,
        object_fn=lambda handler, obj_id: handler[obj_id],
        handler_fn=lambda controller: controller.api.outlets,
        supported_fn=lambda handler, obj_id: handler[obj_id].has_relay,
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
        available_fn=sub_device_disabled,
        control_fn=async_control_poe_port,
        device_info=device_registry_entry,
        entity_cls=UnifiSwitchEntity,
        event_is_on=None,
        event_to_subscribe=None,
        is_on_fn=lambda controller, port: port.poe_mode != "off",
        name_fn=lambda port: f"{port.name} PoE",
        object_fn=lambda handler, obj_id: handler[obj_id],
        handler_fn=lambda controller: controller.api.ports,
        supported_fn=lambda handler, obj_id: handler[obj_id].port_poe,
        unique_id_fn=lambda obj_id: f"{obj_id.split('_', 1)[0]}-poe-{obj_id.split('_', 1)[1]}",
    ),
)

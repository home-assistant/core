"""Switch platform for UniFi Network integration.

Support for controlling power supply of clients which are powered over Ethernet (POE).
Support for controlling network access of clients selected in option flow.
Support for controlling deep packet inspection (DPI) restriction groups.
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from aiounifi.interfaces.api_handlers import ItemEvent
from aiounifi.interfaces.clients import Clients
from aiounifi.interfaces.dpi_restriction_groups import DPIRestrictionGroups
from aiounifi.interfaces.outlets import Outlets
from aiounifi.interfaces.ports import Ports
from aiounifi.models.client import ClientBlockRequest
from aiounifi.models.device import (
    DeviceSetOutletRelayRequest,
    DeviceSetPoePortModeRequest,
)
from aiounifi.models.dpi_restriction_app import DPIRestrictionAppEnableRequest
from aiounifi.models.event import Event, EventKey

from homeassistant.components.switch import DOMAIN, SwitchDeviceClass, SwitchEntity
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

from .const import (
    ATTR_MANUFACTURER,
    BLOCK_SWITCH,
    DOMAIN as UNIFI_DOMAIN,
    DPI_SWITCH,
    OUTLET_SWITCH,
    POE_SWITCH,
)
from .controller import UniFiController
from .unifi_client import UniFiClient

CLIENT_BLOCKED = (EventKey.WIRED_CLIENT_BLOCKED, EventKey.WIRELESS_CLIENT_BLOCKED)
CLIENT_UNBLOCKED = (EventKey.WIRED_CLIENT_UNBLOCKED, EventKey.WIRELESS_CLIENT_UNBLOCKED)

T = TypeVar("T")


@dataclass
class UnifiEntityLoader(Generic[T]):
    """Validate and load entities from different UniFi handlers."""

    allowed_fn: Callable[[UniFiController, str], bool]
    entity_cls: type[UnifiBlockClientSwitch] | type[UnifiDPIRestrictionSwitch] | type[
        UnifiOutletSwitch
    ] | type[UnifiPoePortSwitch] | type[UnifiDPIRestrictionSwitch]
    handler_fn: Callable[[UniFiController], T]
    supported_fn: Callable[[T, str], bool | None]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for UniFi Network integration.

    Switches are controlling network access and switch ports with POE.
    """
    controller: UniFiController = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    controller.entities[DOMAIN] = {
        BLOCK_SWITCH: set(),
        POE_SWITCH: set(),
        DPI_SWITCH: set(),
        OUTLET_SWITCH: set(),
    }

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
    def async_load_entities(loader: UnifiEntityLoader) -> None:
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

            entity = loader.entity_cls(obj_id, controller)
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


class UnifiBlockClientSwitch(SwitchEntity):
    """Representation of a blockable client."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_icon = "mdi:ethernet"
    _attr_should_poll = False

    def __init__(self, obj_id: str, controller: UniFiController) -> None:
        """Set up block switch."""
        controller.entities[DOMAIN][BLOCK_SWITCH].add(obj_id)
        self._obj_id = obj_id
        self.controller = controller

        self._removed = False

        client = controller.api.clients[obj_id]
        self._attr_available = controller.available
        self._attr_is_on = not client.blocked
        self._attr_unique_id = f"{BLOCK_SWITCH}-{obj_id}"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, obj_id)},
            default_manufacturer=client.oui,
            default_name=client.name or client.hostname,
        )

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        self.async_on_remove(
            self.controller.api.clients.subscribe(self.async_signalling_callback)
        )
        self.async_on_remove(
            self.controller.api.events.subscribe(
                self.async_event_callback, CLIENT_BLOCKED + CLIENT_UNBLOCKED
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.controller.signal_remove, self.remove_item
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.controller.signal_options_update, self.options_updated
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.controller.signal_reachable,
                self.async_signal_reachable_callback,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        self.controller.entities[DOMAIN][BLOCK_SWITCH].remove(self._obj_id)

    @callback
    def async_signalling_callback(self, event: ItemEvent, obj_id: str) -> None:
        """Update the clients state."""
        if event == ItemEvent.DELETED:
            self.hass.async_create_task(self.remove_item({self._obj_id}))
            return

        client = self.controller.api.clients[self._obj_id]
        self._attr_is_on = not client.blocked
        self._attr_available = self.controller.available
        self.async_write_ha_state()

    @callback
    def async_event_callback(self, event: Event) -> None:
        """Event subscription callback."""
        if event.mac != self._obj_id:
            return
        if event.key in CLIENT_BLOCKED + CLIENT_UNBLOCKED:
            self._attr_is_on = event.key in CLIENT_UNBLOCKED
        self._attr_available = self.controller.available
        self.async_write_ha_state()

    @callback
    def async_signal_reachable_callback(self) -> None:
        """Call when controller connection state change."""
        self.async_signalling_callback(ItemEvent.ADDED, self._obj_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on connectivity for client."""
        await self.controller.api.request(
            ClientBlockRequest.create(self._obj_id, False)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off connectivity for client."""
        await self.controller.api.request(ClientBlockRequest.create(self._obj_id, True))

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if not self.is_on:
            return "mdi:network-off"
        return "mdi:network"

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if self._obj_id not in self.controller.option_block_clients:
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


class UnifiDPIRestrictionSwitch(SwitchEntity):
    """Representation of a DPI restriction group."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, obj_id: str, controller: UniFiController) -> None:
        """Set up dpi switch."""
        controller.entities[DOMAIN][DPI_SWITCH].add(obj_id)
        self._obj_id = obj_id
        self.controller = controller

        dpi_group = controller.api.dpi_groups[obj_id]
        self._known_app_ids = dpi_group.dpiapp_ids

        self._attr_available = controller.available
        self._attr_is_on = self.calculate_enabled()
        self._attr_name = dpi_group.name
        self._attr_unique_id = dpi_group.id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"unifi_controller_{obj_id}")},
            manufacturer=ATTR_MANUFACTURER,
            model="UniFi Network",
            name="UniFi Network",
        )

    async def async_added_to_hass(self) -> None:
        """Register callback to known apps."""
        self.async_on_remove(
            self.controller.api.dpi_groups.subscribe(self.async_signalling_callback)
        )
        self.async_on_remove(
            self.controller.api.dpi_apps.subscribe(
                self.async_signalling_callback, ItemEvent.CHANGED
            ),
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.controller.signal_remove, self.remove_item
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self.controller.signal_options_update, self.options_updated
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.controller.signal_reachable,
                self.async_signal_reachable_callback,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect object when removed."""
        self.controller.entities[DOMAIN][DPI_SWITCH].remove(self._obj_id)

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

        self._attr_available = self.controller.available
        self._attr_is_on = self.calculate_enabled()
        self.async_write_ha_state()

    @callback
    def async_signal_reachable_callback(self) -> None:
        """Call when controller connection state change."""
        self.async_signalling_callback(ItemEvent.ADDED, self._obj_id)

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        if self.is_on:
            return "mdi:network"
        return "mdi:network-off"

    def calculate_enabled(self) -> bool:
        """Calculate if all apps are enabled."""
        dpi_group = self.controller.api.dpi_groups[self._obj_id]
        return all(
            self.controller.api.dpi_apps[app_id].enabled
            for app_id in dpi_group.dpiapp_ids
            if app_id in self.controller.api.dpi_apps
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Restrict access of apps related to DPI group."""
        dpi_group = self.controller.api.dpi_groups[self._obj_id]
        return await asyncio.gather(
            *[
                self.controller.api.request(
                    DPIRestrictionAppEnableRequest.create(app_id, True)
                )
                for app_id in dpi_group.dpiapp_ids
            ]
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Remove restriction of apps related to DPI group."""
        dpi_group = self.controller.api.dpi_groups[self._obj_id]
        return await asyncio.gather(
            *[
                self.controller.api.request(
                    DPIRestrictionAppEnableRequest.create(app_id, False)
                )
                for app_id in dpi_group.dpiapp_ids
            ]
        )

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_dpi_restrictions:
            await self.remove_item({self._attr_unique_id})

    async def remove_item(self, keys: set) -> None:
        """Remove entity if key is part of set."""
        if self._attr_unique_id not in keys:
            return

        if self.registry_entry:
            er.async_get(self.hass).async_remove(self.entity_id)
        else:
            await self.async_remove(force_remove=True)


class UnifiOutletSwitch(SwitchEntity):
    """Representation of a outlet relay."""

    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, obj_id: str, controller: UniFiController) -> None:
        """Set up UniFi Network entity base."""
        self._device_mac, index = obj_id.split("_", 1)
        self._index = int(index)
        self._obj_id = obj_id
        self.controller = controller

        outlet = self.controller.api.outlets[self._obj_id]
        self._attr_name = outlet.name
        self._attr_is_on = outlet.relay_state
        self._attr_unique_id = f"{self._device_mac}-outlet-{index}"

        device = self.controller.api.devices[self._device_mac]
        self._attr_available = controller.available and not device.disabled
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, device.mac)},
            manufacturer=ATTR_MANUFACTURER,
            model=device.model,
            name=device.name or None,
            sw_version=device.version,
            hw_version=device.board_revision,
        )

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        self.async_on_remove(
            self.controller.api.outlets.subscribe(self.async_signalling_callback)
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.controller.signal_reachable,
                self.async_signal_reachable_callback,
            )
        )

    @callback
    def async_signalling_callback(self, event: ItemEvent, obj_id: str) -> None:
        """Object has new event."""
        device = self.controller.api.devices[self._device_mac]
        outlet = self.controller.api.outlets[self._obj_id]
        self._attr_available = self.controller.available and not device.disabled
        self._attr_is_on = outlet.relay_state
        self.async_write_ha_state()

    @callback
    def async_signal_reachable_callback(self) -> None:
        """Call when controller connection state change."""
        self.async_signalling_callback(ItemEvent.ADDED, self._obj_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable outlet relay."""
        device = self.controller.api.devices[self._device_mac]
        await self.controller.api.request(
            DeviceSetOutletRelayRequest.create(device, self._index, True)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable outlet relay."""
        device = self.controller.api.devices[self._device_mac]
        await self.controller.api.request(
            DeviceSetOutletRelayRequest.create(device, self._index, False)
        )


class UnifiPoePortSwitch(SwitchEntity):
    """Representation of a Power-over-Ethernet source port on an UniFi device."""

    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_icon = "mdi:ethernet"
    _attr_should_poll = False

    def __init__(self, obj_id: str, controller: UniFiController) -> None:
        """Set up UniFi Network entity base."""
        self._device_mac, index = obj_id.split("_", 1)
        self._index = int(index)
        self._obj_id = obj_id
        self.controller = controller

        port = self.controller.api.ports[self._obj_id]
        self._attr_name = f"{port.name} PoE"
        self._attr_is_on = port.poe_mode != "off"
        self._attr_unique_id = f"{self._device_mac}-poe-{index}"

        device = self.controller.api.devices[self._device_mac]
        self._attr_available = controller.available and not device.disabled
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, device.mac)},
            manufacturer=ATTR_MANUFACTURER,
            model=device.model,
            name=device.name or None,
            sw_version=device.version,
            hw_version=device.board_revision,
        )

    async def async_added_to_hass(self) -> None:
        """Entity created."""
        self.async_on_remove(
            self.controller.api.ports.subscribe(self.async_signalling_callback)
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                self.controller.signal_reachable,
                self.async_signal_reachable_callback,
            )
        )

    @callback
    def async_signalling_callback(self, event: ItemEvent, obj_id: str) -> None:
        """Object has new event."""
        device = self.controller.api.devices[self._device_mac]
        port = self.controller.api.ports[self._obj_id]
        self._attr_available = self.controller.available and not device.disabled
        self._attr_is_on = port.poe_mode != "off"
        self.async_write_ha_state()

    @callback
    def async_signal_reachable_callback(self) -> None:
        """Call when controller connection state change."""
        self.async_signalling_callback(ItemEvent.ADDED, self._obj_id)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable POE for client."""
        device = self.controller.api.devices[self._device_mac]
        await self.controller.api.request(
            DeviceSetPoePortModeRequest.create(device, self._index, "auto")
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable POE for client."""
        device = self.controller.api.devices[self._device_mac]
        await self.controller.api.request(
            DeviceSetPoePortModeRequest.create(device, self._index, "off")
        )


UNIFI_LOADERS: tuple[UnifiEntityLoader, ...] = (
    UnifiEntityLoader[Clients](
        allowed_fn=lambda controller, obj_id: obj_id in controller.option_block_clients,
        entity_cls=UnifiBlockClientSwitch,
        handler_fn=lambda contrlr: contrlr.api.clients,
        supported_fn=lambda handler, obj_id: True,
    ),
    UnifiEntityLoader[DPIRestrictionGroups](
        allowed_fn=lambda controller, obj_id: controller.option_dpi_restrictions,
        entity_cls=UnifiDPIRestrictionSwitch,
        handler_fn=lambda controller: controller.api.dpi_groups,
        supported_fn=lambda handler, obj_id: bool(handler[obj_id].dpiapp_ids),
    ),
    UnifiEntityLoader[Outlets](
        allowed_fn=lambda controller, obj_id: True,
        entity_cls=UnifiOutletSwitch,
        handler_fn=lambda controller: controller.api.outlets,
        supported_fn=lambda handler, obj_id: handler[obj_id].has_relay,
    ),
    UnifiEntityLoader[Ports](
        allowed_fn=lambda controller, obj_id: True,
        entity_cls=UnifiPoePortSwitch,
        handler_fn=lambda controller: controller.api.ports,
        supported_fn=lambda handler, obj_id: handler[obj_id].port_poe,
    ),
)

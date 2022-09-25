"""Switch platform for UniFi Network integration.

Support for controlling power supply of clients which are powered over Ethernet (POE).
Support for controlling network access of clients selected in option flow.
Support for controlling deep packet inspection (DPI) restriction groups.
"""

import asyncio
from typing import Any

from aiounifi.interfaces.api_handlers import SOURCE_EVENT
from aiounifi.models.client import ClientBlockRequest
from aiounifi.models.device import (
    DeviceSetOutletRelayRequest,
    DeviceSetPoePortModeRequest,
)
from aiounifi.models.dpi_restriction_app import DPIRestrictionAppEnableRequest
from aiounifi.models.event import EventKey

from homeassistant.components.switch import DOMAIN, SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_NAME
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

from .const import ATTR_MANUFACTURER, DOMAIN as UNIFI_DOMAIN
from .unifi_client import UniFiClient
from .unifi_entity_base import UniFiBase

BLOCK_SWITCH = "block"
DPI_SWITCH = "dpi"
POE_SWITCH = "poe"
OUTLET_SWITCH = "outlet"

CLIENT_BLOCKED = (EventKey.WIRED_CLIENT_BLOCKED, EventKey.WIRELESS_CLIENT_BLOCKED)
CLIENT_UNBLOCKED = (EventKey.WIRED_CLIENT_UNBLOCKED, EventKey.WIRELESS_CLIENT_UNBLOCKED)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches for UniFi Network integration.

    Switches are controlling network access and switch ports with POE.
    """
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
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
        dpi_groups: set = controller.api.dpi_groups,
    ) -> None:
        """Update the values of the controller."""
        add_outlet_entities(controller, async_add_entities, devices)

        if controller.option_block_clients:
            add_block_entities(controller, async_add_entities, clients)

        if controller.option_poe_clients:
            add_poe_entities(controller, async_add_entities, clients, known_poe_clients)

        if controller.option_dpi_restrictions:
            add_dpi_entities(controller, async_add_entities, dpi_groups)

    for signal in (controller.signal_update, controller.signal_options_update):
        config_entry.async_on_unload(
            async_dispatcher_connect(hass, signal, items_added)
        )

    items_added()
    known_poe_clients.clear()


@callback
def add_block_entities(controller, async_add_entities, clients):
    """Add new switch entities from the controller."""
    switches = []

    for mac in controller.option_block_clients:
        if mac in controller.entities[DOMAIN][BLOCK_SWITCH] or mac not in clients:
            continue

        client = controller.api.clients[mac]
        switches.append(UniFiBlockClientSwitch(client, controller))

    if switches:
        async_add_entities(switches)


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

    if switches:
        async_add_entities(switches)


@callback
def add_dpi_entities(controller, async_add_entities, dpi_groups):
    """Add new switch entities from the controller."""
    switches = []

    for group in dpi_groups:
        if (
            group in controller.entities[DOMAIN][DPI_SWITCH]
            or not dpi_groups[group].dpiapp_ids
        ):
            continue

        switches.append(UniFiDPIRestrictionSwitch(dpi_groups[group], controller))

    if switches:
        async_add_entities(switches)


@callback
def add_outlet_entities(controller, async_add_entities, devices):
    """Add new switch entities from the controller."""
    switches = []

    for mac in devices:
        if (
            mac in controller.entities[DOMAIN][OUTLET_SWITCH]
            or not (device := controller.api.devices[mac]).outlet_table
        ):
            continue

        for outlet in device.outlets.values():
            if outlet.has_relay:
                switches.append(UniFiOutletSwitch(device, controller, outlet.index))

    if switches:
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


class UniFiBlockClientSwitch(UniFiClient, SwitchEntity):
    """Representation of a blockable client."""

    DOMAIN = DOMAIN
    TYPE = BLOCK_SWITCH

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, client, controller):
        """Set up block switch."""
        super().__init__(client, controller)

        self._is_blocked = client.blocked

    @callback
    def async_update_callback(self) -> None:
        """Update the clients state."""
        if (
            self.client.last_updated == SOURCE_EVENT
            and self.client.event.key in CLIENT_BLOCKED + CLIENT_UNBLOCKED
        ):
            self._is_blocked = self.client.event.key in CLIENT_BLOCKED

        super().async_update_callback()

    @property
    def is_on(self):
        """Return true if client is allowed to connect."""
        return not self._is_blocked

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on connectivity for client."""
        await self.controller.api.request(
            ClientBlockRequest.create(self.client.mac, False)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off connectivity for client."""
        await self.controller.api.request(
            ClientBlockRequest.create(self.client.mac, True)
        )

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend."""
        if self._is_blocked:
            return "mdi:network-off"
        return "mdi:network"

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if self.client.mac not in self.controller.option_block_clients:
            await self.remove_item({self.client.mac})


class UniFiDPIRestrictionSwitch(UniFiBase, SwitchEntity):
    """Representation of a DPI restriction group."""

    DOMAIN = DOMAIN
    TYPE = DPI_SWITCH

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, dpi_group, controller):
        """Set up dpi switch."""
        super().__init__(dpi_group, controller)

        self._is_enabled = self.calculate_enabled()
        self._known_app_ids = dpi_group.dpiapp_ids

    @property
    def key(self) -> Any:
        """Return item key."""
        return self._item.id

    async def async_added_to_hass(self) -> None:
        """Register callback to known apps."""
        await super().async_added_to_hass()

        apps = self.controller.api.dpi_apps
        for app_id in self._item.dpiapp_ids:
            apps[app_id].register_callback(self.async_update_callback)

    async def async_will_remove_from_hass(self) -> None:
        """Remove registered callbacks."""
        apps = self.controller.api.dpi_apps
        for app_id in self._item.dpiapp_ids:
            apps[app_id].remove_callback(self.async_update_callback)

        await super().async_will_remove_from_hass()

    @callback
    def async_update_callback(self) -> None:
        """Update the DPI switch state.

        Remove entity when no apps are paired with group.
        Register callbacks to new apps.
        Calculate and update entity state if it has changed.
        """
        if not self._item.dpiapp_ids:
            self.hass.async_create_task(self.remove_item({self.key}))
            return

        if self._known_app_ids != self._item.dpiapp_ids:
            self._known_app_ids = self._item.dpiapp_ids

            apps = self.controller.api.dpi_apps
            for app_id in self._item.dpiapp_ids:
                apps[app_id].register_callback(self.async_update_callback)

        if (enabled := self.calculate_enabled()) != self._is_enabled:
            self._is_enabled = enabled
            super().async_update_callback()

    @property
    def unique_id(self):
        """Return a unique identifier for this switch."""
        return self._item.id

    @property
    def name(self) -> str:
        """Return the name of the DPI group."""
        return self._item.name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        if self._is_enabled:
            return "mdi:network"
        return "mdi:network-off"

    def calculate_enabled(self) -> bool:
        """Calculate if all apps are enabled."""
        return all(
            self.controller.api.dpi_apps[app_id].enabled
            for app_id in self._item.dpiapp_ids
            if app_id in self.controller.api.dpi_apps
        )

    @property
    def is_on(self):
        """Return true if DPI group app restriction is enabled."""
        return self._is_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Restrict access of apps related to DPI group."""
        return await asyncio.gather(
            *[
                self.controller.api.request(
                    DPIRestrictionAppEnableRequest.create(app_id, True)
                )
                for app_id in self._item.dpiapp_ids
            ]
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Remove restriction of apps related to DPI group."""
        return await asyncio.gather(
            *[
                self.controller.api.request(
                    DPIRestrictionAppEnableRequest.create(app_id, False)
                )
                for app_id in self._item.dpiapp_ids
            ]
        )

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_dpi_restrictions:
            await self.remove_item({self.key})

    @property
    def device_info(self) -> DeviceInfo:
        """Return a service description for device registry."""
        return DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, f"unifi_controller_{self._item.site_id}")},
            manufacturer=ATTR_MANUFACTURER,
            model="UniFi Network",
            name="UniFi Network",
        )


class UniFiOutletSwitch(UniFiBase, SwitchEntity):
    """Representation of a outlet relay."""

    DOMAIN = DOMAIN
    TYPE = OUTLET_SWITCH

    _attr_device_class = SwitchDeviceClass.OUTLET

    def __init__(self, device, controller, index):
        """Set up outlet switch."""
        super().__init__(device, controller)

        self._outlet_index = index

        self._attr_name = f"{device.name or device.model} {device.outlets[index].name}"
        self._attr_unique_id = f"{device.mac}-outlet-{index}"

    @property
    def is_on(self):
        """Return true if outlet is active."""
        return self._item.outlets[self._outlet_index].relay_state

    @property
    def available(self) -> bool:
        """Return if switch is available."""
        return not self._item.disabled and self.controller.available

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable outlet relay."""
        await self.controller.api.request(
            DeviceSetOutletRelayRequest.create(self._item, self._outlet_index, True)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable outlet relay."""
        await self.controller.api.request(
            DeviceSetOutletRelayRequest.create(self._item, self._outlet_index, False)
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        info = DeviceInfo(
            connections={(CONNECTION_NETWORK_MAC, self._item.mac)},
            manufacturer=ATTR_MANUFACTURER,
            model=self._item.model,
            sw_version=self._item.version,
            hw_version=self._item.board_revision,
        )

        if self._item.name:
            info[ATTR_NAME] = self._item.name

        return info

    async def options_updated(self) -> None:
        """Config entry options are updated, no options to act on."""

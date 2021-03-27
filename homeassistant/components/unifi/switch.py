"""Switch platform for UniFi integration.

Support for controlling power supply of clients which are powered over Ethernet (POE).
Support for controlling network access of clients selected in option flow.
Support for controlling deep packet inspection (DPI) restriction groups.
"""
import logging
from typing import Any

from aiounifi.api import SOURCE_EVENT
from aiounifi.events import (
    WIRED_CLIENT_BLOCKED,
    WIRED_CLIENT_UNBLOCKED,
    WIRELESS_CLIENT_BLOCKED,
    WIRELESS_CLIENT_UNBLOCKED,
)

from homeassistant.components.switch import DOMAIN, SwitchEntity
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_registry import async_entries_for_config_entry
from homeassistant.helpers.restore_state import RestoreEntity

from .const import ATTR_MANUFACTURER, DOMAIN as UNIFI_DOMAIN
from .unifi_client import UniFiClient
from .unifi_entity_base import UniFiBase

_LOGGER = logging.getLogger(__name__)

BLOCK_SWITCH = "block"
DPI_SWITCH = "dpi"
POE_SWITCH = "poe"

CLIENT_BLOCKED = (WIRED_CLIENT_BLOCKED, WIRELESS_CLIENT_BLOCKED)
CLIENT_UNBLOCKED = (WIRED_CLIENT_UNBLOCKED, WIRELESS_CLIENT_UNBLOCKED)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches for UniFi component.

    Switches are controlling network access and switch ports with POE.
    """
    controller = hass.data[UNIFI_DOMAIN][config_entry.entry_id]
    controller.entities[DOMAIN] = {
        BLOCK_SWITCH: set(),
        POE_SWITCH: set(),
        DPI_SWITCH: set(),
    }

    if controller.site_role != "admin":
        return

    # Store previously known POE control entities in case their POE are turned off.
    known_poe_clients = []
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    for entry in async_entries_for_config_entry(entity_registry, config_entry.entry_id):

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
        if controller.option_block_clients:
            add_block_entities(controller, async_add_entities, clients)

        if controller.option_poe_clients:
            add_poe_entities(controller, async_add_entities, clients, known_poe_clients)

        if controller.option_dpi_restrictions:
            add_dpi_entities(controller, async_add_entities, dpi_groups)

    for signal in (controller.signal_update, controller.signal_options_update):
        controller.listeners.append(async_dispatcher_connect(hass, signal, items_added))

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
            or client.sw_mac not in devices
            or not devices[client.sw_mac].ports[client.sw_port].port_poe
            or not devices[client.sw_mac].ports[client.sw_port].poe_enable
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
                and client.sw_mac == client2.sw_mac
                and client.sw_port == client2.sw_port
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


class UniFiPOEClientSwitch(UniFiClient, SwitchEntity, RestoreEntity):
    """Representation of a client that uses POE."""

    DOMAIN = DOMAIN
    TYPE = POE_SWITCH

    def __init__(self, client, controller):
        """Set up POE switch."""
        super().__init__(client, controller)

        self.poe_mode = None
        if client.sw_port and self.port.poe_mode != "off":
            self.poe_mode = self.port.poe_mode

    async def async_added_to_hass(self):
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()

        if self.poe_mode:  # POE is enabled and client in a known state
            return

        if (state := await self.async_get_last_state()) is None:
            return

        self.poe_mode = state.attributes.get("poe_mode")

        if not self.client.sw_mac:
            self.client.raw["sw_mac"] = state.attributes.get("switch")

        if not self.client.sw_port:
            self.client.raw["sw_port"] = state.attributes.get("port")

    @property
    def is_on(self):
        """Return true if POE is active."""
        return self.port.poe_mode != "off"

    @property
    def available(self):
        """Return if switch is available.

        Poe_mode None means its POE state is unknown.
        Sw_mac unavailable means restored client.
        """
        return (
            self.poe_mode is not None
            and self.controller.available
            and self.client.sw_port
            and self.client.sw_mac
            and self.client.sw_mac in self.controller.api.devices
        )

    async def async_turn_on(self, **kwargs):
        """Enable POE for client."""
        await self.device.async_set_port_poe_mode(self.client.sw_port, self.poe_mode)

    async def async_turn_off(self, **kwargs):
        """Disable POE for client."""
        await self.device.async_set_port_poe_mode(self.client.sw_port, "off")

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        attributes = {
            "power": self.port.poe_power,
            "switch": self.client.sw_mac,
            "port": self.client.sw_port,
            "poe_mode": self.poe_mode,
        }
        return attributes

    @property
    def device(self):
        """Shortcut to the switch that client is connected to."""
        return self.controller.api.devices[self.client.sw_mac]

    @property
    def port(self):
        """Shortcut to the switch port that client is connected to."""
        return self.device.ports[self.client.sw_port]

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_poe_clients:
            await self.remove_item({self.client.mac})


class UniFiBlockClientSwitch(UniFiClient, SwitchEntity):
    """Representation of a blockable client."""

    DOMAIN = DOMAIN
    TYPE = BLOCK_SWITCH

    def __init__(self, client, controller):
        """Set up block switch."""
        super().__init__(client, controller)

        self._is_blocked = client.blocked

    @callback
    def async_update_callback(self) -> None:
        """Update the clients state."""
        if (
            self.client.last_updated == SOURCE_EVENT
            and self.client.event.event in CLIENT_BLOCKED + CLIENT_UNBLOCKED
        ):
            self._is_blocked = self.client.event.event in CLIENT_BLOCKED

        super().async_update_callback()

    @property
    def is_on(self):
        """Return true if client is allowed to connect."""
        return not self._is_blocked

    async def async_turn_on(self, **kwargs):
        """Turn on connectivity for client."""
        await self.controller.api.clients.async_unblock(self.client.mac)

    async def async_turn_off(self, **kwargs):
        """Turn off connectivity for client."""
        await self.controller.api.clients.async_block(self.client.mac)

    @property
    def icon(self):
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

    @property
    def key(self) -> Any:
        """Return item key."""
        return self._item.id

    @property
    def unique_id(self):
        """Return a unique identifier for this switch."""
        return self._item.id

    @property
    def name(self) -> str:
        """Return the name of the client."""
        return self._item.name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        if self._item.enabled:
            return "mdi:network"
        return "mdi:network-off"

    @property
    def is_on(self):
        """Return true if client is allowed to connect."""
        return self._item.enabled

    async def async_turn_on(self, **kwargs):
        """Turn on connectivity for client."""
        await self.controller.api.dpi_groups.async_enable(self._item)

    async def async_turn_off(self, **kwargs):
        """Turn off connectivity for client."""
        await self.controller.api.dpi_groups.async_disable(self._item)

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_dpi_restrictions:
            await self.remove_item({self.key})

    @property
    def device_info(self) -> dict:
        """Return a service description for device registry."""
        return {
            "identifiers": {(DOMAIN, f"unifi_controller_{self._item.site_id}")},
            "name": "UniFi Controller",
            "manufacturer": ATTR_MANUFACTURER,
            "model": "UniFi Controller",
            "entry_type": "service",
        }

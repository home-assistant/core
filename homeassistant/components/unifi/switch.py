"""Support for devices connected to UniFi POE."""
import logging

from homeassistant.components.switch import DOMAIN, SwitchDevice
from homeassistant.components.unifi.config_flow import get_controller_from_config_entry
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.restore_state import RestoreEntity

from .unifi_client import UniFiClient

LOGGER = logging.getLogger(__name__)

BLOCK_SWITCH = "block"
POE_SWITCH = "poe"


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Component doesn't support configuration through configuration.yaml."""


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches for UniFi component.

    Switches are controlling network access and switch ports with POE.
    """
    controller = get_controller_from_config_entry(hass, config_entry)
    controller.entities[DOMAIN] = {BLOCK_SWITCH: set(), POE_SWITCH: set()}

    if controller.site_role != "admin":
        return

    switches_off = []

    # Restore clients that is not a part of active clients list.
    entity_registry = await hass.helpers.entity_registry.async_get_registry()
    for entity in entity_registry.entities.values():

        if (
            entity.config_entry_id == config_entry.entry_id
            and entity.unique_id.startswith(f"{POE_SWITCH}-")
        ):

            _, mac = entity.unique_id.split("-", 1)

            if mac in controller.api.clients:
                switches_off.append(entity.unique_id)
                continue

            if mac in controller.api.clients_all:
                client = controller.api.clients_all[mac]
                controller.api.clients.process_raw([client.raw])
                switches_off.append(entity.unique_id)
                continue

    @callback
    def items_added():
        """Update the values of the controller."""
        if controller.option_block_clients or controller.option_poe_clients:
            add_entities(controller, async_add_entities, switches_off)

    for signal in (controller.signal_update, controller.signal_options_update):
        controller.listeners.append(async_dispatcher_connect(hass, signal, items_added))

    items_added()
    switches_off.clear()


@callback
def add_entities(controller, async_add_entities, switches_off):
    """Add new switch entities from the controller."""
    switches = []

    for mac in controller.option_block_clients:

        if mac in controller.entities[DOMAIN][BLOCK_SWITCH]:
            continue

        client = None

        if mac in controller.api.clients:
            client = controller.api.clients[mac]

        elif mac in controller.api.clients_all:
            client = controller.api.clients_all[mac]

        if not client:
            continue

        switches.append(UniFiBlockClientSwitch(client, controller))

    if controller.option_poe_clients:
        devices = controller.api.devices

        for mac in controller.api.clients:

            poe_client_id = f"{POE_SWITCH}-{mac}"

            if mac in controller.entities[DOMAIN][POE_SWITCH]:
                continue

            client = controller.api.clients[mac]

            if poe_client_id not in switches_off and (
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

                if poe_client_id in switches_off:
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


class UniFiPOEClientSwitch(UniFiClient, SwitchDevice, RestoreEntity):
    """Representation of a client that uses POE."""

    TYPE = POE_SWITCH

    def __init__(self, client, controller):
        """Set up POE switch."""
        super().__init__(client, controller)

        self.poe_mode = None
        if self.client.sw_port and self.port.poe_mode != "off":
            self.poe_mode = self.port.poe_mode

    async def async_added_to_hass(self):
        """Call when entity about to be added to Home Assistant."""
        await super().async_added_to_hass()

        state = await self.async_get_last_state()
        if state is None:
            return

        if self.poe_mode is None:
            self.poe_mode = state.attributes["poe_mode"]

        if not self.client.sw_mac:
            self.client.raw["sw_mac"] = state.attributes["switch"]

        if not self.client.sw_port:
            self.client.raw["sw_port"] = state.attributes["port"]

    @property
    def is_on(self):
        """Return true if POE is active."""
        return self.port.poe_mode != "off"

    @property
    def available(self):
        """Return if switch is available.

        Poe_mode None means its poe state is unknown.
        Sw_mac unavailable means restored client.
        """
        return (
            self.poe_mode is None
            or self.client.sw_mac
            and (
                self.controller.available
                and self.client.sw_mac in self.controller.api.devices
            )
        )

    async def async_turn_on(self, **kwargs):
        """Enable POE for client."""
        await self.device.async_set_port_poe_mode(self.client.sw_port, self.poe_mode)

    async def async_turn_off(self, **kwargs):
        """Disable POE for client."""
        await self.device.async_set_port_poe_mode(self.client.sw_port, "off")

    @property
    def device_state_attributes(self):
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
        try:
            return self.device.ports[self.client.sw_port]
        except (AttributeError, KeyError, TypeError):
            LOGGER.warning(
                "Entity %s reports faulty device %s or port %s",
                self.entity_id,
                self.client.sw_mac,
                self.client.sw_port,
            )

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if not self.controller.option_poe_clients:
            await self.async_remove()


class UniFiBlockClientSwitch(UniFiClient, SwitchDevice):
    """Representation of a blockable client."""

    TYPE = BLOCK_SWITCH

    @property
    def is_on(self):
        """Return true if client is allowed to connect."""
        return not self.is_blocked

    async def async_turn_on(self, **kwargs):
        """Turn on connectivity for client."""
        await self.controller.api.clients.async_unblock(self.client.mac)

    async def async_turn_off(self, **kwargs):
        """Turn off connectivity for client."""
        await self.controller.api.clients.async_block(self.client.mac)

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        if self.is_blocked:
            return "mdi:network-off"
        return "mdi:network"

    async def options_updated(self) -> None:
        """Config entry options are updated, remove entity if option is disabled."""
        if self.client.mac not in self.controller.option_block_clients:
            await self.async_remove()

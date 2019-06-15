"""Support for devices connected to UniFi POE."""
from datetime import timedelta
import logging

from homeassistant.components import unifi
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import CONF_CONTROLLER, CONF_SITE_ID, CONTROLLER_ID

SCAN_INTERVAL = timedelta(seconds=15)

LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Component doesn't support configuration through configuration.yaml."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches for UniFi component.

    Switches are controlling network switch ports with Poe.
    """
    controller_id = CONTROLLER_ID.format(
        host=config_entry.data[CONF_CONTROLLER][CONF_HOST],
        site=config_entry.data[CONF_CONTROLLER][CONF_SITE_ID],
    )
    controller = hass.data[unifi.DOMAIN][controller_id]
    switches = {}

    @callback
    def update_controller():
        """Update the values of the controller."""
        update_items(controller, async_add_entities, switches)

    async_dispatcher_connect(hass, controller.event_update, update_controller)

    update_controller()


@callback
def update_items(controller, async_add_entities, switches):
    """Update POE port state from the controller."""
    new_switches = []
    devices = controller.api.devices

    for client_id in controller.api.clients:

        if client_id in switches:
            LOGGER.debug("Updating UniFi switch %s (%s)",
                         switches[client_id].entity_id,
                         switches[client_id].client.mac)
            switches[client_id].async_schedule_update_ha_state()
            continue

        client = controller.api.clients[client_id]
        # Network device with active POE
        if not client.is_wired or client.sw_mac not in devices or \
           not devices[client.sw_mac].ports[client.sw_port].port_poe or \
           not devices[client.sw_mac].ports[client.sw_port].poe_enable or \
           controller.mac == client.mac:
            continue

        # Multiple POE-devices on same port means non UniFi POE driven switch
        multi_clients_on_port = False
        for client2 in controller.api.clients.values():
            if client.mac != client2.mac and \
               client.sw_mac == client2.sw_mac and \
               client.sw_port == client2.sw_port:
                multi_clients_on_port = True
                break

        if multi_clients_on_port:
            continue

        switches[client_id] = UniFiSwitch(client, controller)
        new_switches.append(switches[client_id])
        LOGGER.debug("New UniFi switch %s (%s)", client.hostname, client.mac)

    if new_switches:
        async_add_entities(new_switches)


class UniFiSwitch(SwitchDevice):
    """Representation of a client that uses POE."""

    def __init__(self, client, controller):
        """Set up switch."""
        self.client = client
        self.controller = controller
        self.poe_mode = None
        if self.port.poe_mode != 'off':
            self.poe_mode = self.port.poe_mode

    async def async_update(self):
        """Synchronize state with controller."""
        await self.controller.request_update()

    @property
    def name(self):
        """Return the name of the switch."""
        return self.client.hostname

    @property
    def unique_id(self):
        """Return a unique identifier for this switch."""
        return 'poe-{}'.format(self.client.mac)

    @property
    def is_on(self):
        """Return true if POE is active."""
        return self.port.poe_mode != 'off'

    @property
    def available(self):
        """Return if switch is available."""
        return self.controller.available or \
            self.client.sw_mac in self.controller.api.devices

    async def async_turn_on(self, **kwargs):
        """Enable POE for client."""
        await self.device.async_set_port_poe_mode(
            self.client.sw_port, self.poe_mode)

    async def async_turn_off(self, **kwargs):
        """Disable POE for client."""
        await self.device.async_set_port_poe_mode(self.client.sw_port, 'off')

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = {
            'power': self.port.poe_power,
            'received': self.client.wired_rx_bytes / 1000000,
            'sent': self.client.wired_tx_bytes / 1000000,
            'switch': self.client.sw_mac,
            'port': self.client.sw_port,
            'poe_mode': self.poe_mode
        }
        return attributes

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            'connections': {(CONNECTION_NETWORK_MAC, self.client.mac)}
        }

    @property
    def device(self):
        """Shortcut to the switch that client is connected to."""
        return self.controller.api.devices[self.client.sw_mac]

    @property
    def port(self):
        """Shortcut to the switch port that client is connected to."""
        return self.device.ports[self.client.sw_port]

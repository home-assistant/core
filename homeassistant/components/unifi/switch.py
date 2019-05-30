"""Support for devices connected to UniFi POE."""
import asyncio
from datetime import timedelta
import logging

import async_timeout

from homeassistant.components import unifi
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import CONF_HOST
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

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

    progress = None
    update_progress = set()

    async def request_update(object_id):
        """Request an update."""
        nonlocal progress
        update_progress.add(object_id)

        if progress is not None:
            return await progress

        progress = asyncio.ensure_future(update_controller())
        result = await progress
        progress = None
        update_progress.clear()
        return result

    async def update_controller():
        """Update the values of the controller."""
        tasks = [async_update_items(
            controller, async_add_entities, request_update,
            switches, update_progress
        )]
        await asyncio.wait(tasks)

    await update_controller()


async def async_update_items(controller, async_add_entities,
                             request_controller_update, switches,
                             progress_waiting):
    """Update POE port state from the controller."""
    import aiounifi

    @callback
    def update_switch_state():
        """Tell switches to reload state."""
        for client_id, client in switches.items():
            if client_id not in progress_waiting:
                client.async_schedule_update_ha_state()

    try:
        with async_timeout.timeout(4):
            await controller.api.clients.update()
            await controller.api.devices.update()

    except aiounifi.LoginRequired:
        try:
            with async_timeout.timeout(5):
                await controller.api.login()
        except (asyncio.TimeoutError, aiounifi.AiounifiException):
            if controller.available:
                controller.available = False
                update_switch_state()
            return

    except (asyncio.TimeoutError, aiounifi.AiounifiException):
        if controller.available:
            LOGGER.error('Unable to reach controller %s', controller.host)
            controller.available = False
            update_switch_state()
        return

    if not controller.available:
        LOGGER.info('Reconnected to controller %s', controller.host)
        controller.available = True

    new_switches = []
    devices = controller.api.devices
    for client_id in controller.api.clients:

        if client_id in progress_waiting:
            continue

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

        switches[client_id] = UniFiSwitch(
            client, controller, request_controller_update)
        new_switches.append(switches[client_id])
        LOGGER.debug("New UniFi switch %s (%s)", client.hostname, client.mac)

    if new_switches:
        async_add_entities(new_switches)


class UniFiSwitch(SwitchDevice):
    """Representation of a client that uses POE."""

    def __init__(self, client, controller, request_controller_update):
        """Set up switch."""
        self.client = client
        self.controller = controller
        self.poe_mode = None
        if self.port.poe_mode != 'off':
            self.poe_mode = self.port.poe_mode
        self.async_request_controller_update = request_controller_update

    async def async_update(self):
        """Synchronize state with controller."""
        await self.async_request_controller_update(self.client.mac)

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

"""
Support for devices connected to Unifi POE.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.unifi/"""

import asyncio
import logging

from homeassistant.components.switch import SwitchDevice
from homeassistant.components import unifi
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

DEPENDENCIES = ['unifi']

LOGGER = logging.getLogger(__name__)

STORAGE_KEY = 'unifi.poe_off_clients'
STORAGE_VERSION = 1
SAVE_DELAY = 10


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Component doesn't support configuration through configuration.yaml."""
    pass


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up switches for UniFi component.

    Switches are controlling switch ports with Poe.
    """
    controller = hass.data[unifi.DOMAIN][config_entry.data['host']]
    switches = {}

    store = hass.helpers.storage.Store(STORAGE_VERSION, STORAGE_KEY)
    switches_off = await store.async_load()
    if switches_off is None:
        switches_off = {}
    controller.api.clients.process_raw(list(switches_off.values()))

    progress = None
    update_progress = set()

    async def request_update(object_id):
        """Request an update."""
        nonlocal progress
        update_progress.add(object_id)

        if progress is not None:
            return await progress

        progress = asyncio.ensure_future(controller.request_update())
        result = await progress
        await update_controller()
        progress = None
        update_progress.clear()
        return result

    async def update_controller():
        """"""
        tasks = [async_update_items(
            controller, async_add_entities, request_update,
            switches, switches_off, update_progress, store
        )]
        await asyncio.wait(tasks)

    await update_controller()


async def async_update_items(controller, async_add_entities,
                             request_controller_update, switches, switches_off,
                             progress_waiting, store):
    """Update POE port state from the controller."""
    if not controller.available:
        for client_id, client in switches.items():
            if client_id not in progress_waiting:
                client.async_schedule_update_ha_state()
        return

    new_switches = []
    devices = controller.api.devices
    for client_id in controller.api.clients:

        if client_id not in switches:
            client = controller.api.clients[client_id]

            if client.is_wired and \
               client.sw_mac in devices and \
               devices[client.sw_mac].ports[client.sw_port].poe_enable is not None:
                switches[client_id] = UniFiSwitch(
                    client, controller, request_controller_update)
                new_switches.append(switches[client_id])
                LOGGER.debug("New UniFi switch %s (%s)",
                             client.hostname, client.mac)

        elif client_id not in progress_waiting:
            LOGGER.debug("Updating UniFi switch %s (%s)",
                         switches[client_id].entity_id,
                         switches[client_id].client.mac)
            switches[client_id].async_schedule_update_ha_state()

    update_storage = False
    for device in controller.api.devices.values():
        for port in device.ports.values():

            if port.port_poe and port.poe_mode == 'off':
                for client in controller.api.clients.values():
                    if client.mac not in switches_off and \
                       device.mac == client.sw_mac and \
                       port.port_idx == client.sw_port:
                        switches_off[client.mac] = client.raw
                        update_storage = True

            elif port.port_poe and port.poe_mode is not None:
                for client in controller.api.clients.values():
                    if client.mac in switches_off and \
                       device.mac == client.sw_mac and \
                       port.port_idx == client.sw_port:
                        del switches_off[client.mac]
                        update_storage = True

    @callback
    def _data_to_save():
        """Update storage with devices that has got its' POE turned off."""
        return switches_off
    if update_storage:
        store.async_delay_save(_data_to_save, SAVE_DELAY)

    if new_switches:
        async_add_entities(new_switches)


class UniFiSwitch(SwitchDevice):
    """Representation of a client that uses POE."""

    def __init__(self, client, controller, request_controller_update):
        """Set up switch."""
        self.client = client
        self.controller = controller
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
        await self.device.async_set_port_poe_mode(self.client.sw_port, 'auto')

    async def async_turn_off(self, **kwargs):
        """Disable POE for client."""
        await self.device.async_set_port_poe_mode(self.client.sw_port, 'off')

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = {}
        if self.client.is_wired:
            attributes['POE'] = self.port.poe_power
            attributes['received'] = self.client.wired_rx_bytes / 1000000
            attributes['transferred'] = self.client.wired_tx_bytes / 1000000
        return attributes

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            'connections': {(CONNECTION_NETWORK_MAC, self.client.mac)},
            'name': self.name,
        }

    @property
    def device(self):
        """Shortcut to switch that client is connected to."""
        return self.controller.api.devices[self.client.sw_mac]

    @property
    def port(self):
        """Shortcut to switch port that client is connected to."""
        return self.device.ports[self.client.sw_port]

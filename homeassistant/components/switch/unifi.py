"""
Support for devices connected to UniFi POE.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/switch.unifi/
"""

import asyncio
import logging

from datetime import timedelta

from homeassistant.components.switch import SwitchDevice
from homeassistant.components import unifi
from homeassistant.core import callback
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC

DEPENDENCIES = ['unifi']
SCAN_INTERVAL = timedelta(seconds=15)

LOGGER = logging.getLogger(__name__)

STORAGE_KEY = 'unifi.poe_off_clients'
STORAGE_VERSION = 1
SAVE_DELAY = 10


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
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
    controller.api.clients.process_raw([switch['data']
                                        for switch in switches_off.values()]
                                      )

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
        """Update the values of the controller."""
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

        if client_id in progress_waiting:
            continue

        if client_id in switches:
            LOGGER.debug("Updating UniFi switch %s (%s)",
                         switches[client_id].entity_id,
                         switches[client_id].client.mac)
            switches[client_id].async_schedule_update_ha_state()
            continue

        client = controller.api.clients[client_id]
        if not client.is_wired or client.sw_mac not in devices or \
           not devices[client.sw_mac].ports[client.sw_port].port_poe or \
           not devices[client.sw_mac].ports[client.sw_port].poe_enable and \
           client.mac not in switches_off:
            continue

        poe_mode = None
        if client.mac in switches_off:
            poe_mode = switches_off[client.mac]['poe_mode']

        switches[client_id] = UniFiSwitch(
            client, controller, request_controller_update, poe_mode)
        new_switches.append(switches[client_id])
        LOGGER.debug("New UniFi switch %s (%s)", client.hostname, client.mac)

    @callback
    def _data_to_save():
        """Update storage with devices that has got its' POE off."""
        return switches_off

    for switch in switches.values():
        if switch.port.poe_mode == 'off' and \
           switch.client.mac not in switches_off:
            switches_off[switch.client.mac] = {
                'data': switch.client.raw,
                'poe_mode': switch.poe_mode
            }
            store.async_delay_save(_data_to_save, SAVE_DELAY)

        elif switch.port.poe_mode != 'off' and \
           switch.client.mac in switches_off:
            del switches_off[switch.client.mac]
            store.async_delay_save(_data_to_save, SAVE_DELAY)

    if new_switches:
        async_add_entities(new_switches)


class UniFiSwitch(SwitchDevice):
    """Representation of a client that uses POE."""

    def __init__(self, client, controller,
                 request_controller_update, poe_mode):
        """Set up switch."""
        self.client = client
        self.controller = controller
        self.poe_mode = poe_mode
        self.async_request_controller_update = request_controller_update

    async def async_update(self):
        """Synchronize state with controller."""
        if self.poe_mode is None and self.port.poe_mode != 'off':
            self.poe_mode = self.port.poe_mode
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
            'sent': self.client.wired_tx_bytes / 1000000
        }
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

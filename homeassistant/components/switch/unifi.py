""""""

import asyncio
import logging

import async_timeout

from homeassistant.components.switch import SwitchDevice
from homeassistant.components import unifi

DEPENDENCIES = ['unifi']

LOGGER = logging.getLogger(__name__)


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

    progress = None
    update_progress = set()

    async def request_update(object_id):
        """"""
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
        """"""
        tasks = [async_update_items(
            hass, controller, async_add_entities, request_update,
            switches, update_progress
        )]
        await asyncio.wait(tasks)

    await update_controller()


async def async_update_items(hass, controller, async_add_entities,
                             request_controller_update, switches,
                             progress_waiting):
    """Update either groups or lights from the bridge."""
    import aiounifi
    print('update')

    try:
        with async_timeout.timeout(4):
            await controller.api.clients.update()
            await controller.api.devices.update()

    except (asyncio.TimeoutError, aiounifi.AiounifiException):
        if not controller.available:
            return

        LOGGER.error('Unable to reach controller %s', controller.host)
        controller.available = False

        for client_id, client in switches.items():
            if client_id not in progress_waiting:
                client.async_schedule_update_ha_state()

        return

    if not controller.available:
        LOGGER.info('Reconnected to controller %s', controller.host)
        controller.available = True

    new_switches = []
    for client_id in controller.api.clients:
        if client_id not in switches:
            client = controller.api.clients[client_id]
            devices = controller.api.devices

            if client.is_wired and \
               devices[client.sw_mac].ports[client.sw_port].poe_enable:
                switches[client_id] = UniFiSwitch(
                    client, controller, request_controller_update)
                new_switches.append(switches[client_id])
                LOGGER.info("New UniFi switch %s (%s)",
                            client.hostname, client.mac)

        elif client_id not in progress_waiting:
            LOGGER.debug("Updating UniFi switch %s (%s)",
                         switches[client_id].entity_id,
                         switches[client_id].client.mac)
            switches[client_id].async_schedule_update_ha_state()

    if new_switches:
        async_add_entities(new_switches)


class UniFiSwitch(SwitchDevice):
    """"""

    def __init__(self, client, controller, request_controller_update):
        """Set up switch."""
        self.client = client
        self.controller = controller
        self.async_request_controller_update = request_controller_update

    async def async_update(self):
        """Synchronize state with bridge."""
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
        """Return true if switch is on."""
        devices = self.controller.api.devices
        client = self.client
        state = devices[client.sw_mac].ports[client.sw_port].up
        return state

    async def async_turn_on(self, **kwargs):
        url = 's/{site}/cmd/devmgr'
        data = {
            'mac': self.client.sw_mac,
            'port_idx': self.client.sw_port
        }
        print('on', url, data)

    async def async_turn_off(self, **kwargs):
        print('off')

    @property
    def device_info(self):
        """Return the device info."""
        return None

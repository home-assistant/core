"""
Component for interacting with a Lutron RadioRA 2 system.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/lutron/
"""
import asyncio
import logging

from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['pylutron==0.1.0']

DOMAIN = 'lutron'

_LOGGER = logging.getLogger(__name__)

LUTRON_CONTROLLER = 'lutron_controller'
LUTRON_DEVICES = 'lutron_devices'


def setup(hass, base_config):
    """Set up the Lutron component."""
    from pylutron import Lutron

    hass.data[LUTRON_CONTROLLER] = None
    hass.data[LUTRON_DEVICES] = {'light': []}

    config = base_config.get(DOMAIN)
    hass.data[LUTRON_CONTROLLER] = Lutron(
        config['lutron_host'],
        config['lutron_user'],
        config['lutron_password']
    )
    hass.data[LUTRON_CONTROLLER].load_xml_db()
    hass.data[LUTRON_CONTROLLER].connect()
    _LOGGER.info("Connected to Main Repeater at %s", config['lutron_host'])

    # Sort our devices into types
    for area in hass.data[LUTRON_CONTROLLER].areas:
        for output in area.outputs:
            hass.data[LUTRON_DEVICES]['light'].append((area.name, output))

    for component in ('light',):
        discovery.load_platform(hass, component, DOMAIN, None, base_config)
    return True


class LutronDevice(Entity):
    """Representation of a Lutron device entity."""

    def __init__(self, area_name, lutron_device, controller):
        """Initialize the device."""
        self._lutron_device = lutron_device
        self._controller = controller
        self._area_name = area_name

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Register callbacks."""
        self.hass.async_add_job(
            self._controller.subscribe, self._lutron_device,
            self._update_callback
        )

    def _update_callback(self, _device):
        """Run when invoked by pylutron when the device state changes."""
        self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        return "{} {}".format(self._area_name, self._lutron_device.name)

    @property
    def should_poll(self):
        """No polling needed."""
        return False

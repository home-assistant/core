"""
Component for interacting with a Lutron RadioRA 2 system using
pylutron (http://github.com/thecynic/pylutron).

"""

import logging
import xml.etree.ElementTree as ET
import telnetlib
import time

from collections import defaultdict
from requests.exceptions import RequestException

from homeassistant import bootstrap

from homeassistant.components import group
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.loader import get_component

REQUIREMENTS = ['pylutron']

DOMAIN = "lutron"

# List of component names (string) your component depends upon.
DEPENDENCIES = ['group', 'light']

_LOGGER = logging.getLogger(__name__)

LUTRON_CONTROLLER = None

LUTRON_DEVICES = {'light': []}
LUTRON_GROUPS = {}

def setup(hass, base_config):
    """Setup our skeleton component."""
    global LUTRON_CONTROLLER

    from pylutron import Lutron

    config = base_config.get(DOMAIN)
    LUTRON_CONTROLLER = Lutron(
        config['lutron_host'],
        config['lutron_user'],
        config['lutron_password']
    )
    LUTRON_CONTROLLER.load_xml_db()
    LUTRON_CONTROLLER.connect()
    _LOGGER.info("CONNECTED?!")

    # Sort our devices into types
    for area in LUTRON_CONTROLLER.areas:
      if area.name not in LUTRON_GROUPS:
        gr = group.Group(hass, area.name, [])
        LUTRON_GROUPS[area.name] = gr
      for output in area.outputs:
        LUTRON_DEVICES['light'].append((area.name, output))

    for component in ('light',):
        discovery.load_platform(hass, component, DOMAIN, None, base_config)
    return True


class LutronDevice(Entity):
    """Representation of a Lutron device entity."""

    def __init__(self, hass, area_name, lutron_device, controller):
        """Initialize the device."""
        self._lutron_device = lutron_device
        self._controller = controller
        self._area_name = area_name

        self.update()
        self._controller.subscribe(self._lutron_device, self._update_callback)

    def _update_callback(self, _device):
        """Callback invoked by pylutron when the device state changes."""
        self.update_ha_state()

    @property
    def name(self):
        """Return the name of the device."""
        return self._lutron_device.name

    @property
    def should_poll(self):
        """No polling needed."""
        return False

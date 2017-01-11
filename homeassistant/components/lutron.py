"""
Component for interacting with a Lutron RadioRA 2 system.

Uses pylutron (http://github.com/thecynic/pylutron).
"""

import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components import group
from homeassistant.helpers import discovery
from homeassistant.helpers.entity import Entity
from homeassistant.const import (CONF_HOST, CONF_USERNAME,
                                 CONF_PASSWORD)

REQUIREMENTS = ["https://github.com/thecynic/pylutron/"
                "archive/v0.1.0.zip#pylutron==0.1.0"]

DOMAIN = "lutron"

# List of component names (string) your component depends upon.
DEPENDENCIES = ['group', 'light']

_LOGGER = logging.getLogger(__name__)

LUTRON_CONTROLLER = None

LUTRON_DEVICES = {'light': []}
LUTRON_GROUPS = {}

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    })
})


def setup(hass, base_config):
    """Setup our skeleton component."""
    global LUTRON_CONTROLLER

    from pylutron import Lutron

    config = base_config.get(DOMAIN)
    LUTRON_CONTROLLER = Lutron(
        config[DOMAIN].get(CONF_HOST),
        config[DOMAIN].get(CONF_USERNAME),
        config[DOMAIN].get(CONF_PASSWORD)
    )
    LUTRON_CONTROLLER.load_xml_db()
    LUTRON_CONTROLLER.connect()
    _LOGGER.info("Connected to Lutron")

    # Sort our devices into types
    for area in LUTRON_CONTROLLER.areas:
        if area.name not in LUTRON_GROUPS:
            LUTRON_GROUPS[area.name] = group.Group(hass, area.name, [])
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

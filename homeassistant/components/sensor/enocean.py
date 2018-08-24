"""
Support for EnOcean sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.enocean/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_ID)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.components import enocean

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'EnOcean sensor'
DEPENDENCIES = ['enocean']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an EnOcean sensor device."""
    dev_id = config.get(CONF_ID)
    devname = config.get(CONF_NAME)

    add_entities([EnOceanSensor(dev_id, devname)])


class EnOceanSensor(enocean.EnOceanDevice, Entity):
    """Representation of an EnOcean sensor device such as a power meter."""

    def __init__(self, dev_id, devname):
        """Initialize the EnOcean sensor device."""
        enocean.EnOceanDevice.__init__(self)
        self.stype = "powersensor"
        self.power = None
        self.dev_id = dev_id
        self.which = -1
        self.onoff = -1
        self.devname = devname

    @property
    def name(self):
        """Return the name of the device."""
        return 'Power %s' % self.devname

    def value_changed(self, value):
        """Update the internal state of the device."""
        self.power = value
        self.schedule_update_ha_state()

    @property
    def state(self):
        """Return the state of the device."""
        return self.power

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return 'W'

"""
Support for Ripple sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.ripple/
"""
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['python-ripple-api==0.0.2']

CONF_ADDRESS = 'address'
CONF_ATTRIBUTION = "Data provided by ripple.com"

DEFAULT_NAME = 'Ripple Balance'

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Ripple.com sensors."""
    address = config.get(CONF_ADDRESS)
    name = config.get(CONF_NAME)

    add_devices([RippleSensor(name, address)], True)


class RippleSensor(Entity):
    """Representation of an Ripple.com sensor."""

    def __init__(self, name, address):
        """Initialize the sensor."""
        self._name = name
        self.address = address
        self._state = None
        self._unit_of_measurement = 'XRP'

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }

    def update(self):
        """Get the latest state of the sensor."""
        from pyripple import get_balance
        self._state = get_balance(self.address)

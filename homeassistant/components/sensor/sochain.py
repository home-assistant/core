"""
Support for sochain sensors. (LTC, DOGE, DASH, BTC)

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.sochain/
"""
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['python-sochain-api==0.0.1']

CONF_ADDRESS = 'address'
CONF_NETWORK = 'network'
CONF_ATTRIBUTION = "Data provided by chain.so"

DEFAULT_NAME = 'Crypto Balance'

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the sochain sensors."""
    address = config.get(CONF_ADDRESS)
    network = config.get(CONF_NETWORK)
    name = config.get(CONF_NAME)

    add_devices([SochainSensor(name, network, address)], True)


class SochainSensor(Entity):
    """Representation of a Sochain sensor."""

    def __init__(self, name, network, address):
        """Initialize the sensor."""
        self._name = name
        self.network = network
        self.address = address
        self._state = None
        self._unit_of_measurement = network.upper()

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
        from pysochain import get_balance
        self._state = get_balance(self.network, self.address)

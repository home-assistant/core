"""
Support for Blockchain.info sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.blockchain/
"""
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, ATTR_ATTRIBUTION)
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['python-blockchain-api==0.0.2']

_LOGGER = logging.getLogger(__name__)

CONF_ADDRESSES = 'addresses'
CONF_ATTRIBUTION = "Data provided by blockchain.info"

DEFAULT_NAME = 'Bitcoin Balance'

ICON = 'mdi:currency-btc'

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESSES): [cv.string],
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Blockchain.info sensors."""
    from pyblockchain import validate_address

    addresses = config.get(CONF_ADDRESSES)
    name = config.get(CONF_NAME)

    for address in addresses:
        if not validate_address(address):
            _LOGGER.error("Bitcoin address is not valid: %s", address)
            return False

    add_entities([BlockchainSensor(name, addresses)], True)


class BlockchainSensor(Entity):
    """Representation of a Blockchain.info sensor."""

    def __init__(self, name, addresses):
        """Initialize the sensor."""
        self._name = name
        self.addresses = addresses
        self._state = None
        self._unit_of_measurement = 'BTC'

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
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {
            ATTR_ATTRIBUTION: CONF_ATTRIBUTION,
        }

    def update(self):
        """Get the latest state of the sensor."""
        from pyblockchain import get_balance
        self._state = get_balance(self.addresses)

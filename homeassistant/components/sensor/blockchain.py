"""
Support for Blockchain.info sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.blockchain/
"""
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

REQUIREMENTS = ['python-blockchain-api==0.0.1']
CONF_ADDRESSES = 'addresses'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESSES): [cv.string]
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the etherscan sensors."""
    add_devices([BlockchainSensor('Bitcoin Balance',
                                  config.get(CONF_ADDRESSES))])


class BlockchainSensor(Entity):
    """Representation of an Etherscan.io sensor."""

    def __init__(self, name, addresses):
        """Initialize the sensor."""
        self._name = name
        self.addresses = addresses
        self._state = None
        self._unit_of_measurement = 'BTC'
        self.update()

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

    def update(self):
        """Get the latest state of the sensor."""
        from pyblockchain import get_balance
        self._state = get_balance(self.addresses)

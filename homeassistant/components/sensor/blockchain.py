"""
Support for Blockchain.info sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.blockchain/
"""
import logging
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

REQUIREMENTS = ['python-blockchain-api==0.0.2']
_LOGGER = logging.getLogger(__name__)
CONF_ADDRESSES = 'addresses'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESSES): [cv.string]
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the blockchain sensors."""
    from pyblockchain import validate_address
    addresses = config.get(CONF_ADDRESSES)
    for address in addresses:
        if not validate_address(address):
            _LOGGER.error("Bitcoin address is not valid: " + address)
            return False
    add_devices([BlockchainSensor('Bitcoin Balance', addresses)])


class BlockchainSensor(Entity):
    """Representation of a blockchain.info sensor."""

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

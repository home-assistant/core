"""Support for Etherscan sensors."""
from datetime import timedelta

from pyetherscan import get_balance
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION, CONF_ADDRESS, CONF_NAME, CONF_TOKEN
import homeassistant.helpers.config_validation as cv

ATTRIBUTION = "Data provided by etherscan.io"

CONF_TOKEN_ADDRESS = "token_address"

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_TOKEN): cv.string,
        vol.Optional(CONF_TOKEN_ADDRESS): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Etherscan.io sensors."""
    address = config.get(CONF_ADDRESS)
    name = config.get(CONF_NAME)
    token = config.get(CONF_TOKEN)
    token_address = config.get(CONF_TOKEN_ADDRESS)

    if token:
        token = token.upper()
        if not name:
            name = f"{token} Balance"
    if not name:
        name = "ETH Balance"

    add_entities([EtherscanSensor(name, address, token, token_address)], True)


class EtherscanSensor(SensorEntity):
    """Representation of an Etherscan.io sensor."""

    def __init__(self, name, address, token, token_address):
        """Initialize the sensor."""
        self._name = name
        self._address = address
        self._token_address = token_address
        self._token = token
        self._state = None
        self._unit_of_measurement = self._token or "ETH"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement this sensor expresses itself in."""
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the sensor."""
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    def update(self):
        """Get the latest state of the sensor."""

        if self._token_address:
            self._state = get_balance(self._address, self._token_address)
        elif self._token:
            self._state = get_balance(self._address, self._token)
        else:
            self._state = get_balance(self._address)

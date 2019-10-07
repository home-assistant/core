"""Support for Ripple sensors."""
from datetime import timedelta

from pyripple import get_balance
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_ADDRESS, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

ATTRIBUTION = "Data provided by ripple.com"

DEFAULT_NAME = "Ripple Balance"

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_ADDRESS): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Ripple.com sensors."""
    address = config.get(CONF_ADDRESS)
    name = config.get(CONF_NAME)

    add_entities([RippleSensor(name, address)], True)


class RippleSensor(Entity):
    """Representation of an Ripple.com sensor."""

    def __init__(self, name, address):
        """Initialize the sensor."""
        self._name = name
        self.address = address
        self._state = None
        self._unit_of_measurement = "XRP"

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
        return {ATTR_ATTRIBUTION: ATTRIBUTION}

    def update(self):
        """Get the latest state of the sensor."""

        balance = get_balance(self.address)
        if balance is not None:
            self._state = balance

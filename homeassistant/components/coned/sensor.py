"""Platform for sensor integration."""
from datetime import timedelta
import logging

from coned import Meter, MeterError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME, ENERGY_KILO_WATT_HOUR
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by ConEdison"

CONF_METER_NUMBER = "meter_number"

SCAN_INTERVAL = timedelta(minutes=15)

DEFAULT_NAME = "ConEdison Current Energy Usage"
SENSOR_ICON = "mdi:counter"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_METER_NUMBER): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    meter_number = config[CONF_METER_NUMBER]

    try:
        meter = Meter(meter_number)

    except MeterError:
        _LOGGER.error("Unable to create ConEd meter")
        return

    name = config[CONF_NAME]

    add_entities([CurrentEnergyUsageSensor(meter, name)], True)

    _LOGGER.debug("ConEd meter_number = %s", meter_number)


class CurrentEnergyUsageSensor(Entity):
    """Representation of the sensor."""

    def __init__(self, meter, name):
        """Initialize the sensor."""
        self._state = None
        self._attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}
        self._name = name
        self._available = None
        self.meter = meter

    @property
    def unique_id(self):
        """Return a unique, HASS-friendly identifier for this entity."""
        return self.meter.meter_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return SENSOR_ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_KILO_WATT_HOUR

    def update(self):
        """Fetch new state data for the sensor."""
        try:
            last_read = self.meter.last_read()

            self._state = last_read
            self._available = True

            _LOGGER.debug(
                "%s = %s %s", self.name, self._state, self.unit_of_measurement
            )
        except MeterError as err:
            self._available = False

            _LOGGER.error("Unexpected coned meter error: %s", err)

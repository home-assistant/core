"""Platform for sensor integration."""
from datetime import timedelta
import logging

from oru import Meter, MeterError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import ENERGY_KILO_WATT_HOUR
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_METER_NUMBER = "meter_number"

SCAN_INTERVAL = timedelta(minutes=15)

SENSOR_NAME = "ORU Current Energy Usage"
SENSOR_ICON = "mdi:counter"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_METER_NUMBER): cv.string})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    meter_number = config[CONF_METER_NUMBER]

    try:
        meter = Meter(meter_number)

    except MeterError:
        _LOGGER.error("Unable to create Oru meter")
        return

    add_entities([CurrentEnergyUsageSensor(meter)], True)

    _LOGGER.debug("Oru meter_number = %s", meter_number)


class CurrentEnergyUsageSensor(SensorEntity):
    """Representation of the sensor."""

    def __init__(self, meter):
        """Initialize the sensor."""
        self._state = None
        self._available = None
        self.meter = meter

    @property
    def unique_id(self):
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return self.meter.meter_id

    @property
    def name(self):
        """Return the name of the sensor."""
        return SENSOR_NAME

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

            _LOGGER.error("Unexpected oru meter error: %s", err)

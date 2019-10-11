"""Platform for sensor integration."""
import logging

from oru import Meter
from oru import MeterError
from homeassistant.const import ENERGY_WATT_HOUR
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_METER_NUMBER = "meter_number"

COMPONENT_NAME = "Orange and Rockland Utility Real Time Energy Usage"
COMPONENT_ICON = "mdi:counter"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    meter_number = str(config.get(CONF_METER_NUMBER, None))
    meter = Meter(meter_number)

    add_entities([RealTimeEnergyUsageSensor(meter)])

    _LOGGER.debug("meter_number = %s", meter_number)


class RealTimeEnergyUsageSensor(Entity):
    """Representation of the sensor."""

    def __init__(self, meter):
        """Initialize the sensor."""
        self._state = None
        self._available = None
        self.meter = meter

    @property
    def name(self):
        """Return the name of the sensor."""
        return COMPONENT_NAME

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return COMPONENT_ICON

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return ENERGY_WATT_HOUR

    def update(self):
        """Fetch new state data for the sensor."""
        try:
            last_read = self.meter.last_read()

            _LOGGER.info(
                "Oru meter last_read = %s %s", last_read, self.unit_of_measurement
            )

            self._state = last_read
            self._available = True
        except MeterError as err:
            self._available = False
            _LOGGER.error("Unexpected oru meter error: %s", str(err))

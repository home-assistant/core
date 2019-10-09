"""Platform for sensor integration."""
import logging
from oru import Meter
from homeassistant.const import ENERGY_WATT_HOUR
from homeassistant.helpers.entity import Entity


_LOGGER = logging.getLogger(__name__)

CONF_METER = "meter"


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""
    global meter_id

    add_entities([RealTimeEnergyUsageSensor()])

    meter_id = str(config.get(CONF_METER, None))
    _LOGGER.debug("meter_id = %s", meter_id)


class RealTimeEnergyUsageSensor(Entity):
    """Representation of the sensor."""

    def __init__(self):
        """Initialize the sensor."""
        self._state = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return "Real Time Energy Usage"

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

        meter = Meter(meter_id)
        last_read = meter.last_read()

        _LOGGER.info("last_read = %s %s", last_read, self.unit_of_measurement)

        self._state = last_read

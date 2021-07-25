"""Platform for sensor integration."""
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.util import Throttle

from .const import DOMAIN, PRICE_CODE

SCAN_INTERVAL = timedelta(hours=1)
MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Barry sensor."""
    barry_connection = hass.data[DOMAIN]
    price_code = hass.data[PRICE_CODE]
    async_add_entities([BarrySensor(barry_connection, price_code)], True)


class BarrySensor(SensorEntity):
    """Representation of a Sensor."""

    _attr_unit_of_measurement = "DKK/kWh"

    def __init__(self, barry_home, price_code):
        """Initialize the sensor."""
        self._barry_home = barry_home
        self.price_code = price_code
        self._attr_name = "Electricity price Barry"

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._attr_state = self._barry_home.update_price_data(self.price_code)

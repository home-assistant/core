"""Platform for sensor integration."""
from datetime import timedelta
import logging

from homeassistant.helpers.entity import Entity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(hours=1)
MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Barry sensor."""
    barry_connection = hass.data.get(DOMAIN)
    price_code = hass.data.get("price_code")
    async_add_entities([BarrySensor(barry_connection, price_code)], True)


class BarrySensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, barry_home, price_code):
        """Initialize the sensor."""
        self._barry_home = barry_home
        self.price_code = price_code
        self._state = None
        self._name = "Barry"
        self._device_state_attributes = {}

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return self._device_state_attributes

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Electricity price {self._name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def model(self):
        """Return the model of the sensor."""
        return "Price Sensor"

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return "DKK/kWh"

    def update(self):
        """Fetch new state data for the sensor.

        This is the only method that should fetch new data for Home Assistant.
        """
        self._state = self._barry_home.update_price_data(self.price_code)

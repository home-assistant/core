"""The ELV USB-WDE1 sensor data."""

import logging

import usbwde

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    PERCENTAGE,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config: ConfigEntry, async_add_devices
):
    """Set up the sensor platform."""
    async_add_devices(
        [Temperature(index) for index in range(9)]
        + [Humidity(index) for index in range(9)],
        True,
    )


class _Sensor(Entity):
    """Representation of a Sensor connected to the receiver."""

    def __init__(self, index: int):
        """Initialize the sensor."""
        self._wde = usbwde.WDE()
        self._index = index
        self._state = self._wde.latest().sensors[self._index]

    def update(self):
        """Fetch new state data for the sensor."""
        self._state = self._wde.latest().sensors[self._index]


class Temperature(_Sensor):
    """The supported devices are combined temperature and humidity sensors. This is the virtual temperature sensor."""

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Temperature sensor {self._index+1}"

    @property
    def state(self) -> int:
        """Return the most recent reported value."""
        return self._state.temperature

    @property
    def device_class(self) -> str:
        """Identify as the temperature feeler of the combined sensor."""
        return DEVICE_CLASS_TEMPERATURE

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return TEMP_CELSIUS


class Humidity(_Sensor):
    """The supported devices are combined temperature and humidity sensors. This is the virtual humidity sensor."""

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Humidity sensor {self._index+1}"

    @property
    def state(self) -> int:
        """Return the most recent reported value."""
        return self._state.humidity

    @property
    def device_class(self) -> str:
        """Identify as the humidity feeler of the combined sensor."""
        return DEVICE_CLASS_HUMIDITY

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return PERCENTAGE

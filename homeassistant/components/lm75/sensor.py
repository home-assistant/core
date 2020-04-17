"""Support for LM75 temperature sensor."""
import logging

import smbus  # pylint: disable=import-error

from homeassistant.const import (
    DEVICE_CLASS_TEMPERATURE,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.temperature import display_temp

_LOGGER = logging.getLogger(__name__)

LM75_TEMP_REGISTER = 0
LM75_CONF_REGISTER = 1
LM75_THYST_REGISTER = 2
LM75_TOS_REGISTER = 3
REGISTER = [
    LM75_TEMP_REGISTER,
    LM75_CONF_REGISTER,
    LM75_THYST_REGISTER,
    LM75_TOS_REGISTER,
]

DEFAULT_NAME = "LM75 Temperature Sensor"
DEFAULT_I2C_ADDRESS = 0x48
DEFAULT_I2C_BUS = 1
DEFAULT_REGISTER = LM75_TEMP_REGISTER


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Set up the platform from config_entry."""
    name = config_entry.data["name"]
    async_add_entities([LM75(name)], True)


class LM75(Entity):
    """Implementation of the LM75 sensor."""

    def __init__(self, name):
        """Initialize the sensor."""
        self._state = None
        self._name = name
        self._address = DEFAULT_I2C_ADDRESS
        self._bus = smbus.SMBus(DEFAULT_I2C_BUS)
        self._register = DEFAULT_REGISTER

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def device_class(self):
        """Return the device class."""
        return DEVICE_CLASS_TEMPERATURE

    def update(self):
        """Get the latest data from the sensor."""
        temp_celsius = self.__read_temperature()
        if temp_celsius is not None:
            self._state = display_temp(
                self.hass, temp_celsius, TEMP_CELSIUS, PRECISION_TENTHS
            )
        else:
            _LOGGER.warning("Problem reading temperature from sensor.")

    @staticmethod
    def regdata_to_float(regdata):
        """Convert raw sensor data to temperature."""
        return (regdata / 32.0) / 8.0

    def __read_temperature(self):
        """Read raw data from the SMBus and convert it to human readable temperature."""
        raw = self._bus.read_word_data(self._address, self._register) & 0xFFFF
        raw = ((raw << 8) & 0xFF00) + (raw >> 8)
        return LM75.regdata_to_float(raw)

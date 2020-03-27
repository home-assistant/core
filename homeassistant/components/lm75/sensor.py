"""Support for LM75 temperature sensor."""
import logging

import smbus  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME,
    DEVICE_CLASS_TEMPERATURE,
    PRECISION_TENTHS,
    TEMP_CELSIUS,
)
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.temperature import display_temp

_LOGGER = logging.getLogger(__name__)

CONF_I2C_ADDRESS = "i2c_address"
CONF_I2C_BUS = "i2c_bus"
CONF_REGISTER = "register"

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

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): vol.Coerce(int),
        vol.Optional(CONF_I2C_BUS, default=DEFAULT_I2C_BUS): vol.Coerce(int),
        vol.Optional(CONF_REGISTER, default=DEFAULT_REGISTER): vol.In(REGISTER),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the sensor platform."""

    name = config.get(CONF_NAME)
    i2c_address = config.get(CONF_I2C_ADDRESS)
    bus_number = config.get(CONF_I2C_BUS)
    register = config.get(CONF_REGISTER)

    _LOGGER.info(
        "Setup of temperature sensor at address %s with bus number %s is complete",
        i2c_address,
        bus_number,
    )

    add_entities([LM75(name, i2c_address, bus_number, register)])


class LM75(Entity):
    """Implementation of the LM75 sensor."""

    def __init__(self, name, address, busnum, register):
        """Initialize the sensor."""
        self._state = None
        self._name = name
        self._address = address
        self._bus = smbus.SMBus(busnum)
        self._register = register

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

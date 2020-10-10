"""Platform for Time of Flight sensor VL53L1X from STMicroelectronics."""

import asyncio
from functools import partial
import logging

from VL53L1X2 import VL53L1X  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.components import rpi_gpio
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_NAME, LENGTH_MILLIMETERS
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

CONF_I2C_ADDRESS = "i2c_address"
CONF_I2C_BUS = "i2c_bus"
CONF_XSHUT = "xshut"

DEFAULT_NAME = "VL53L1X"
DEFAULT_I2C_ADDRESS = 0x29
DEFAULT_I2C_BUS = 1
DEFAULT_XSHUT = 16
DEFAULT_RANGE = 2

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): vol.Coerce(int),
        vol.Optional(CONF_I2C_BUS, default=DEFAULT_I2C_BUS): vol.Coerce(int),
        vol.Optional(CONF_XSHUT, default=DEFAULT_XSHUT): cv.positive_int,
    }
)


def init_tof_0(xshut, sensor):
    """XSHUT port LOW resets the device."""
    sensor.open()
    rpi_gpio.setup_output(xshut)
    rpi_gpio.write_output(xshut, 0)


def init_tof_1(xshut):
    """XSHUT port HIGH enables the device."""
    rpi_gpio.setup_output(xshut)
    rpi_gpio.write_output(xshut, 1)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Reset and initialize the VL53L1X ToF Sensor from STMicroelectronics."""

    name = config.get(CONF_NAME)
    bus_number = config.get(CONF_I2C_BUS)
    i2c_address = config.get(CONF_I2C_ADDRESS)
    unit = LENGTH_MILLIMETERS
    xshut = config.get(CONF_XSHUT)

    sensor = await hass.async_add_executor_job(partial(VL53L1X, bus_number))
    await hass.async_add_executor_job(init_tof_0, xshut, sensor)
    await asyncio.sleep(0.01)
    await hass.async_add_executor_job(init_tof_1, xshut)
    await asyncio.sleep(0.01)

    dev = [VL53L1XSensor(sensor, name, unit, i2c_address)]

    async_add_entities(dev, True)


class VL53L1XSensor(Entity):
    """Implementation of VL53L1X sensor."""

    def __init__(self, vl53l1x_sensor, name, unit, i2c_address):
        """Initialize the sensor."""
        self._name = name
        self._unit_of_measurement = unit
        self.vl53l1x_sensor = vl53l1x_sensor
        self.i2c_address = i2c_address
        self._state = None
        self.init = True

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self) -> int:
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def update(self):
        """Get the latest measurement and update state."""
        if self.init:
            self.vl53l1x_sensor.add_sensor(self.i2c_address, self.i2c_address)
            self.init = False
        self.vl53l1x_sensor.start_ranging(self.i2c_address, DEFAULT_RANGE)
        self.vl53l1x_sensor.update(self.i2c_address)
        self.vl53l1x_sensor.stop_ranging(self.i2c_address)
        self._state = self.vl53l1x_sensor.distance

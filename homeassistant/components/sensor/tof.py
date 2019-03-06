"""Platform for Time of Flight sensor VL53L1X."""

import asyncio
import logging
from functools import partial

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.components import rpi_gpio
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['VL53L1X2==0.1.5']

DEPENDENCIES = ['rpi_gpio']

_LOGGER = logging.getLogger(__name__)

LENGTH_MILLIMETERS = 'mm'

CONF_I2C_ADDRESS = 'i2c_address'
CONF_I2C_BUS = 'i2c_bus'
CONF_XSHUT = 'xshut'

DEFAULT_NAME = 'VL53L1X'
DEFAULT_I2C_ADDRESS = 0x29
DEFAULT_I2C_BUS = 1
DEFAULT_XSHUT = 16
DEFAULT_RANGE = 2

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME,
                 default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_I2C_ADDRESS,
                 default=DEFAULT_I2C_ADDRESS): vol.Coerce(int),
    vol.Optional(CONF_I2C_BUS,
                 default=DEFAULT_I2C_BUS): vol.Coerce(int),
    vol.Optional(CONF_XSHUT,
                 default=DEFAULT_XSHUT): cv.positive_int,
})


def init_tof(xshut, level):
    """XSHUT port LOW resets the device."""
    rpi_gpio.setup_output(xshut)
    rpi_gpio.write_output(xshut, level)


async def async_setup_platform(hass,
                               config,
                               async_add_entities,
                               discovery_info=None):
    """Reset and initialize the VL53L1X ToF Sensor from STMicroelectronics."""
    from VL53L1X2 import VL53L1X  # pylint: disable=import-error

    name = config.get(CONF_NAME)
    bus_number = config.get(CONF_I2C_BUS)
    i2c_address = config.get(CONF_I2C_ADDRESS)
    unit = LENGTH_MILLIMETERS
    xshut = config.get(CONF_XSHUT)

    await hass.async_add_executor_job(
        init_tof, xshut, 0
    )
    await asyncio.sleep(0.01)
    await hass.async_add_executor_job(
        init_tof, xshut, 1
    )
    await asyncio.sleep(0.01)

    sensor = await hass.async_add_executor_job(
        partial(VL53L1X, bus_number)
    )

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
        _LOGGER.info(
            "Setup-1 of VL53L1X light sensor at %s is complete",
            self.i2c_address
        )

    def init(self):
        self.vl53l1x_sensor.open()
        self.vl53l1x_sensor.add_sensor(self.i2c_address, self.i2c_address)
        _LOGGER.info(
            "Setup-2 of VL53L1X light sensor at %s is complete",
            self.i2c_address
        )

    async def async_added_to_hass(self):
        """Handle entity about to be added to hass event."""
        await self.hass.async_add_executor_job(
            self.init
        )

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

    def measure(self):
        """Get the latest measurement from VL53L1X."""
        _LOGGER.info(
            "Starting measure of VL53L1X light sensor at %s",
            self.i2c_address
        )
        self.vl53l1x_sensor.start_ranging(self.i2c_address, DEFAULT_RANGE)
        self.vl53l1x_sensor.update(self.i2c_address)
        self.vl53l1x_sensor.stop_ranging(self.i2c_address)

    async def async_update(self):
        """Get the latest measurement and update state."""
        await self.hass.async_add_executor_job(
            self.measure
        )
        self._state = self.vl53l1x_sensor.distance

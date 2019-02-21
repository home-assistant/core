"""
Platform for tof
Time of Flight - VL53L1X Laser Ranger.

For more details about this platform, please refer to
https://github.com/josemotta/vl53l1x-python

Fixed setup for current driver version:

- DEFAULT_RANGE is always LONG
- DEFAULT_I2C_BUS is always 1
- A GPIO connected to VL53L1X XSHUT input resets the device.
- XSHUT starts pulsing LOW and after that it is kept HIGH all time.

"""
from datetime import timedelta
from functools import partial
import logging
import time
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components import rpi_gpio
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['smbus2==0.2.2', 'VL53L1X2==0.1.5']

DEPENDENCIES = ['rpi_gpio']

_LOGGER = logging.getLogger(__name__)

LENGTH_MILIMETERS = 'mm'

CONF_I2C_ADDRESS = 'i2c_address'
CONF_I2C_BUS = 'i2c_bus'
CONF_RANGE = 'range'
CONF_XSHUT = 'xshut'

DEFAULT_NAME = 'VL53L1X'
DEFAULT_I2C_ADDRESS = 0x29
DEFAULT_XSHUT = 16
DEFAULT_SENSOR_ID = 123

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME,
                 default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_I2C_ADDRESS,
                 default=DEFAULT_I2C_ADDRESS): vol.Coerce(int),
    vol.Optional(CONF_XSHUT,
                 default=DEFAULT_XSHUT): cv.positive_int,
})


async def async_setup_platform(hass,
                               config,
                               async_add_entities,
                               discovery_info=None):
    """Setup the VL53L1X ToF Sensor from ST."""
    from VL53L1X2 import VL53L1X

    name = config.get(CONF_NAME)
    unit = LENGTH_MILIMETERS
    xshut = config.get(CONF_XSHUT)

    #  pulse XSHUT port and keep it HIGH
    rpi_gpio.setup_output(xshut)
    rpi_gpio.write_output(xshut, 0)
    time.sleep(0.01)
    rpi_gpio.write_output(xshut, 1)
    time.sleep(0.01)

    sensor = await hass.async_add_job(partial(VL53L1X))
    dev = [VL53L1XSensor(sensor, name, unit)]

    async_add_entities(dev, True)


class VL53L1XSensor(Entity):
    """Implementation of VL53L1X sensor."""

    def __init__(self, vl53l1x_sensor, name, unit):
        """Initialize the sensor."""
        self._name = name
        self._unit_of_measurement = unit
        self.vl53l1x_sensor = vl53l1x_sensor
        self._state = None

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

    async def async_update(self):
        """Get the latest measurement from VL53L1X and update state."""

        self.vl53l1x_sensor.open()
        self.vl53l1x_sensor.add_sensor(DEFAULT_SENSOR_ID, DEFAULT_I2C_ADDRESS)
        self.vl53l1x_sensor.start_ranging(DEFAULT_SENSOR_ID, 2)
        self.vl53l1x_sensor.update(DEFAULT_SENSOR_ID)
        self.vl53l1x_sensor.stop_ranging(DEFAULT_SENSOR_ID)

        _LOGGER.info("VL53L1X sensor update: %s",
                      self.vl53l1x_sensor.distance)

        self._state = self.vl53l1x_sensor.distance

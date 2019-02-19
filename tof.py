"""
Platform for tof
Time of Flight - VL53L1X Laser Ranger.

For more details about this platform, please refer to
https://github.com/josemotta/vl53l1x-python

Fixed setup for initial version:

- DEFAULT_RANGE is always LONG
- DEFAULT_I2C_BUS is always 1
- A GPIO output port is connected to VL53L1X XSHUT input, in order to reset device.
- XSHUT starts pulsing LOW and after that it is kept HIGH all time.

"""
from datetime import timedelta
from functools import partial
import logging
import time
from datetime import datetime
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.components import rpi_gpio
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

REQUIREMENTS = ['smbus2==0.2.2', 'VL53L1X2==0.1.5']

DEPENDENCIES = ['rpi_gpio']

_LOGGER = logging.getLogger(__name__)

LENGTH_MILIMETERS = 'mm' # type: str

CONF_I2C_ADDRESS = 'i2c_address'
CONF_I2C_BUS = 'i2c_bus'
CONF_RANGE = 'range'
CONF_XSHUT = 'xshut'

DEFAULT_NAME = 'VL53L1X'
DEFAULT_I2C_ADDRESS = 0x29
#DEFAULT_I2C_BUS = 1
#DEFAULT_RANGE = 2
DEFAULT_XSHUT = 16
DEFAULT_SENSOR_ID = 123

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=5)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): vol.Coerce(int),
#    vol.Optional(CONF_I2C_BUS, default=DEFAULT_I2C_BUS): vol.Coerce(int),
#    vol.Optional(CONF_RANGE, default=DEFAULT_RANGE): cv.positive_int,
    vol.Optional(CONF_XSHUT, default=DEFAULT_XSHUT): cv.positive_int,
})

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Setup the VL53L1X ToF Sensor from ST."""
    import smbus # pylint: disable=import-error
    from VL53L1X2 import VL53L1X # pylint: disable=import-error

    name = config.get(CONF_NAME)
    #bus_number = config.get(CONF_I2C_BUS)
    #i2c_address = config.get(CONF_I2C_ADDRESS)
    unit = LENGTH_MILIMETERS
    #range = config.get(CONF_RANGE)
    xshut = config.get(CONF_XSHUT)
    sensor_id = DEFAULT_SENSOR_ID

    # pulse XSHUT port and keep it HIGH
    rpi_gpio.setup_output(xshut)
    rpi_gpio.write_output(xshut, 0)
    time.sleep(0.01)
    rpi_gpio.write_output(xshut, 1)
    time.sleep(0.01)

    tof = VL53L1X()
    tof.open() # Initialise the i2c bus and configure the sensor
    tof.add_sensor(sensor_id, DEFAULT_I2C_ADDRESS) # add a VL53L1X device
    tof.start_ranging(sensor_id, 2) # Start ranging, driver use always LONG range

    distance_mm = tof.get_distance(sensor_id)  # Grab the range in mm
    _LOGGER.warning("Time: {}\tVL53L1X: {} mm".format(datetime.utcnow().strftime("%S.%f"), distance_mm))

    tof.stop_ranging(sensor_id)
   
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

        d = self.vl53l1x_sensor.distance

        #_LOGGER.info("VL53L1X sensor update: %s", d)

        self._state = d

        """ TODO: do we really need this?
        await self.hass.async_add_job(partial(self.vl53l1x_sensor.add_sensor, DEFAULT_SENSOR_ID, self.i2c_address))
        await self.hass.async_add_job(partial(self.vl53l1x_sensor.start_ranging,  DEFAULT_SENSOR_ID, 2))
        await self.hass.async_add_job(partial(self.vl53l1x_sensor.update, DEFAULT_SENSOR_ID))

        if self.vl53l1x_sensor.sample_ok:
            self._state = self.vl53l1x_sensor.distance(DEFAULT_SENSOR_ID) / 10
        else:
            _LOGGER.warning("Bad Update of sensor.%s: %s",
                            self.name, self.vl53l1x_sensor.distance(DEFAULT_SENSOR_ID))
        
        await self.hass.async_add_job(partial(self.vl53l1x_sensor.stop_ranging,  DEFAULT_SENSOR_ID))
        """
        

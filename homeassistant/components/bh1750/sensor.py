"""Support for BH1750 light sensor."""
from functools import partial
import logging

from i2csense.bh1750 import BH1750  # pylint: disable=import-error
import smbus
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME, DEVICE_CLASS_ILLUMINANCE, LIGHT_LUX
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_I2C_ADDRESS = "i2c_address"
CONF_I2C_BUS = "i2c_bus"
CONF_OPERATION_MODE = "operation_mode"
CONF_SENSITIVITY = "sensitivity"
CONF_DELAY = "measurement_delay_ms"
CONF_MULTIPLIER = "multiplier"

# Operation modes for BH1750 sensor (from the datasheet). Time typically 120ms
# In one time measurements, device is set to Power Down after each sample.
CONTINUOUS_LOW_RES_MODE = "continuous_low_res_mode"
CONTINUOUS_HIGH_RES_MODE_1 = "continuous_high_res_mode_1"
CONTINUOUS_HIGH_RES_MODE_2 = "continuous_high_res_mode_2"
ONE_TIME_LOW_RES_MODE = "one_time_low_res_mode"
ONE_TIME_HIGH_RES_MODE_1 = "one_time_high_res_mode_1"
ONE_TIME_HIGH_RES_MODE_2 = "one_time_high_res_mode_2"
OPERATION_MODES = {
    CONTINUOUS_LOW_RES_MODE: (0x13, True),  # 4lx resolution
    CONTINUOUS_HIGH_RES_MODE_1: (0x10, True),  # 1lx resolution.
    CONTINUOUS_HIGH_RES_MODE_2: (0x11, True),  # 0.5lx resolution.
    ONE_TIME_LOW_RES_MODE: (0x23, False),  # 4lx resolution.
    ONE_TIME_HIGH_RES_MODE_1: (0x20, False),  # 1lx resolution.
    ONE_TIME_HIGH_RES_MODE_2: (0x21, False),  # 0.5lx resolution.
}

DEFAULT_NAME = "BH1750 Light Sensor"
DEFAULT_I2C_ADDRESS = "0x23"
DEFAULT_I2C_BUS = 1
DEFAULT_MODE = CONTINUOUS_HIGH_RES_MODE_1
DEFAULT_DELAY_MS = 120
DEFAULT_SENSITIVITY = 69  # from 31 to 254

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): cv.string,
        vol.Optional(CONF_I2C_BUS, default=DEFAULT_I2C_BUS): vol.Coerce(int),
        vol.Optional(CONF_OPERATION_MODE, default=DEFAULT_MODE): vol.In(
            OPERATION_MODES
        ),
        vol.Optional(CONF_SENSITIVITY, default=DEFAULT_SENSITIVITY): cv.positive_int,
        vol.Optional(CONF_DELAY, default=DEFAULT_DELAY_MS): cv.positive_int,
        vol.Optional(CONF_MULTIPLIER, default=1.0): vol.Range(min=0.1, max=10),
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the BH1750 sensor."""

    name = config[CONF_NAME]
    bus_number = config[CONF_I2C_BUS]
    i2c_address = config[CONF_I2C_ADDRESS]
    operation_mode = config[CONF_OPERATION_MODE]

    bus = smbus.SMBus(bus_number)

    sensor = await hass.async_add_executor_job(
        partial(
            BH1750,
            bus,
            i2c_address,
            operation_mode=operation_mode,
            measurement_delay=config[CONF_DELAY],
            sensitivity=config[CONF_SENSITIVITY],
            logger=_LOGGER,
        )
    )
    if not sensor.sample_ok:
        _LOGGER.error("BH1750 sensor not detected at %s", i2c_address)
        return False

    dev = [BH1750Sensor(sensor, name, LIGHT_LUX, config[CONF_MULTIPLIER])]
    _LOGGER.info(
        "Setup of BH1750 light sensor at %s in mode %s is complete",
        i2c_address,
        operation_mode,
    )

    async_add_entities(dev, True)


class BH1750Sensor(SensorEntity):
    """Implementation of the BH1750 sensor."""

    def __init__(self, bh1750_sensor, name, unit, multiplier=1.0):
        """Initialize the sensor."""
        self._name = name
        self._unit_of_measurement = unit
        self._multiplier = multiplier
        self.bh1750_sensor = bh1750_sensor
        if self.bh1750_sensor.light_level >= 0:
            self._state = int(round(self.bh1750_sensor.light_level))
        else:
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
        """Return the unit of measurement of the sensor."""
        return self._unit_of_measurement

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_ILLUMINANCE

    async def async_update(self):
        """Get the latest data from the BH1750 and update the states."""
        await self.hass.async_add_executor_job(self.bh1750_sensor.update)
        if self.bh1750_sensor.sample_ok and self.bh1750_sensor.light_level >= 0:
            self._state = int(round(self.bh1750_sensor.light_level * self._multiplier))
        else:
            _LOGGER.warning(
                "Bad Update of sensor.%s: %s", self.name, self.bh1750_sensor.light_level
            )

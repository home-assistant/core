"""
Support for BMP280 pressure and temperature sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.BMP280/
"""

import logging

DEPENDENCIES = ['rpi_i2c']

import homeassistant.components.rpi_i2c as i2c
import voluptuous as vol
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.const import TEMP_CELSIUS
from homeassistant.components.sensor import PLATFORM_SCHEMA

CONF_TEMP_NAME = 'temp_name'
CONF_PRESS_NAME = 'press_name'
CONF_TEMP_ADJ   = 'temp_adj'
CONF_PRESS_ADJ = 'press_adj'
CONF_ADDRESS = 'address'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_TEMP_NAME, default="Temperature"): cv.string,
    vol.Optional(CONF_PRESS_NAME, default="Pressure"): cv.string,
    vol.Optional(CONF_ADDRESS, default=0x76): vol.Coerce(int),
    vol.Optional(CONF_TEMP_ADJ, default=0.0): vol.Coerce(float),
    vol.Optional(CONF_PRESS_ADJ, default=0.0): vol.Coerce(float)
})

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup BMP280 sensor."""
    bmp280_base = Bmp280(config.get(CONF_ADDRESS))
    add_devices([Bmp280Temperature(bmp280_base, config.get(CONF_TEMP_NAME), config.get(CONF_TEMP_ADJ)),
                 Bmp280Pressure(bmp280_base, config.get(CONF_PRESS_NAME), config.get(CONF_PRESS_ADJ))])


class Bmp280Temperature(Entity):
    """Implementation of an BMP280 temperature sensor."""
    def __init__(self, bmp280_base, name, adj):
        self._bmp280_base = bmp280_base
        self._name = name
        self._adj = adj
        self._unit_of_measurement = TEMP_CELSIUS

    @property
    def should_poll(self):
        return True

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._bmp280_base.read_temperature() + self._adj

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class Bmp280Pressure(Entity):
    """Implementation of an BMP280 temperature sensor."""
    def __init__(self, bmp280_base, name, adj):
        self._bmp280_base = bmp280_base
        self._name = name
        self._adj = adj
        self._unit_of_measurement = "hPa"

    @property
    def should_poll(self):
        return True

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._bmp280_base.read_pressure() + self._adj

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit_of_measurement


class Bmp280:

    CONFIG = 0x60  # Stand_by time = 250 ms, IIR filter off
    CONTROL = 0x27  # Normal mode, osr_t = 1 and osr_p = 1

    CONFIG_ADDR = 0xF5
    CONTROL_ADDR = 0xF4
    TEMPERATURE_ADDR = 0xFA
    PRESSURE_ADDR = 0xF7

    COMPENSATION_DATA_ADDR = 0x88

    DIG_T1 = 0
    DIG_T2 = 0
    DIG_T3 = 0
    DIG_P1 = 0
    DIG_P2 = 0
    DIG_P3 = 0
    DIG_P4 = 0
    DIG_P5 = 0
    DIG_P6 = 0
    DIG_P7 = 0
    DIG_P8 = 0
    DIG_P9 = 0

    def __init__(self, address):
        self.address = address
        self._bus = i2c
        self._bus.write_byte_data(address, self.CONTROL_ADDR, self.CONTROL)
        self._bus.write_byte_data(address, self.CONFIG_ADDR, self.CONFIG)
        self.read_calibration_data()
        self._tfine = 0

    @staticmethod
    def get_signed_16_from_array(a, b):
        val = a[b + 1] << 8 | a[b]
        mask = 1 << 15
        return (val ^ mask) - mask

    @staticmethod
    def get_unsigned_16_from_array(a, b):
        return a[b + 1] << 8 | a[b]

    def read_unsigned_32(self, c):
        d = self._bus.read_i2c_block_data(self.address, c, 3)
        return ((d[0] << 16) | (d[1] << 8) | (d[2] << 8)) >> 4

    def read_calibration_data(self):
        a = self._bus.read_i2c_block_data(self.address, self.COMPENSATION_DATA_ADDR, 24)
        self.DIG_T1 = self.get_unsigned_16_from_array(a, 0)
        self.DIG_T2 = self.get_signed_16_from_array(a, 2)
        self.DIG_T3 = self.get_signed_16_from_array(a, 4)
        self.DIG_P1 = self.get_unsigned_16_from_array(a, 6)
        self.DIG_P2 = self.get_signed_16_from_array(a, 8)
        self.DIG_P3 = self.get_signed_16_from_array(a, 10)
        self.DIG_P4 = self.get_signed_16_from_array(a, 12)
        self.DIG_P5 = self.get_signed_16_from_array(a, 14)
        self.DIG_P6 = self.get_signed_16_from_array(a, 16)
        self.DIG_P7 = self.get_signed_16_from_array(a, 18)
        self.DIG_P8 = self.get_signed_16_from_array(a, 20)
        self.DIG_P9 = self.get_signed_16_from_array(a, 22)

    def read_temperature(self):
        adc_T = self.read_unsigned_32(self.TEMPERATURE_ADDR)
        TMP_PART1 = (((adc_T >> 3) - (self.DIG_T1 << 1)) * self.DIG_T2) >> 11
        TMP_PART2 = (((((adc_T >> 4) - (self.DIG_T1)) * ((adc_T >> 4) - (self.DIG_T1))) >> 12) * ((self.DIG_T3)) >> 14)
        TMP_FINE = TMP_PART1 + TMP_PART2
        self._tfine = TMP_FINE
        return round(((TMP_FINE * 5 + 128) >> 8) / 100, 1)

    def read_pressure(self):
        if self._tfine == 0:
            self.read_temperature()
        adc_P = self.read_unsigned_32(self.PRESSURE_ADDR)
        var1 = self._tfine - 128000
        var2 = var1 * var1 * self.DIG_P6
        var2 = var2 + ((var1 * self.DIG_P5) << 17)
        var2 = var2 + ((self.DIG_P4) << 35)
        var1 = ((var1 * var1 * self.DIG_P3) >> 8) + ((var1 * self.DIG_P2) << 12)
        var1 = ((((1) << 47) + var1)) * (self.DIG_P1) >> 33
        if var1 == 0:
            return 0
        p = 1048576 - adc_P
        p = (((p << 31) - var2) * 3125) // var1
        var1 = ((self.DIG_P9) * (p >> 13) * (p >> 13)) >> 25
        var2 = ((self.DIG_P8) * p) >> 19
        p = ((p + var1 + var2) >> 8) + ((self.DIG_P7) << 4)
        return round(p / 25600, 1)

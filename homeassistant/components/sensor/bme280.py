"""
Support for BME280 temperature, humidity and pressure sensor.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.bme280/
"""
import asyncio
from datetime import timedelta
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    TEMP_FAHRENHEIT, CONF_NAME, CONF_MONITORED_CONDITIONS)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle
from homeassistant.util.temperature import celsius_to_fahrenheit

REQUIREMENTS = ['smbus-cffi==0.5.1']

_LOGGER = logging.getLogger(__name__)

CONF_I2C_ADDRESS = 'i2c_address'
CONF_I2C_BUS = 'i2c_bus'
CONF_OVERSAMPLING_TEMP = 'oversampling_temperature'
CONF_OVERSAMPLING_PRES = 'oversampling_pressure'
CONF_OVERSAMPLING_HUM = 'oversampling_humidity'
CONF_OPERATION_MODE = 'operation_mode'
CONF_T_STANDBY = 'time_standby'
CONF_FILTER_MODE = 'filter_mode'
CONF_DELTA_TEMP = 'delta_temperature'

DEFAULT_NAME = 'BME280 Sensor'
DEFAULT_I2C_ADDRESS = '0x76'
DEFAULT_I2C_BUS = 1
DEFAULT_OVERSAMPLING_TEMP = 1  # Temperature oversampling x 1
DEFAULT_OVERSAMPLING_PRES = 1  # Pressure oversampling x 1
DEFAULT_OVERSAMPLING_HUM = 1  # Humidity oversampling x 1
DEFAULT_OPERATION_MODE = 3  # Normal mode (forced mode: 2)
DEFAULT_T_STANDBY = 5  # Tstandby 5ms
DEFAULT_FILTER_MODE = 0  # Filter off
DEFAULT_DELTA_TEMP = 0.

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=3)

SENSOR_TEMP = 'temperature'
SENSOR_HUMID = 'humidity'
SENSOR_PRESS = 'pressure'
SENSOR_TYPES = {
    SENSOR_TEMP: ['Temperature', None],
    SENSOR_HUMID: ['Humidity', '%'],
    SENSOR_PRESS: ['Pressure', 'mb']
}
DEFAULT_MONITORED = [SENSOR_TEMP, SENSOR_HUMID, SENSOR_PRESS]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_I2C_ADDRESS, default=DEFAULT_I2C_ADDRESS): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=DEFAULT_MONITORED):
        vol.All(cv.ensure_list, [vol.In(SENSOR_TYPES)]),
    vol.Optional(CONF_I2C_BUS, default=DEFAULT_I2C_BUS): vol.Coerce(int),
    vol.Optional(CONF_OVERSAMPLING_TEMP,
                 default=DEFAULT_OVERSAMPLING_TEMP): vol.Coerce(int),
    vol.Optional(CONF_OVERSAMPLING_PRES,
                 default=DEFAULT_OVERSAMPLING_PRES): vol.Coerce(int),
    vol.Optional(CONF_OVERSAMPLING_HUM,
                 default=DEFAULT_OVERSAMPLING_HUM): vol.Coerce(int),
    vol.Optional(CONF_OPERATION_MODE,
                 default=DEFAULT_OPERATION_MODE): vol.Coerce(int),
    vol.Optional(CONF_T_STANDBY,
                 default=DEFAULT_T_STANDBY): vol.Coerce(int),
    vol.Optional(CONF_FILTER_MODE,
                 default=DEFAULT_FILTER_MODE): vol.Coerce(int),
    vol.Optional(CONF_DELTA_TEMP,
                 default=DEFAULT_DELTA_TEMP): vol.Coerce(float),
})


# noinspection PyUnusedLocal
@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up the BME280 sensor."""
    SENSOR_TYPES[SENSOR_TEMP][1] = hass.config.units.temperature_unit
    name = config.get(CONF_NAME)
    i2c_address = config.get(CONF_I2C_ADDRESS)

    try:
        # noinspection PyUnresolvedReferences
        import smbus
        bus = smbus.SMBus(config.get(CONF_I2C_BUS))
    except ImportError as exc:
        _LOGGER.error("ImportError: %s", exc)
        return False

    sensor = yield from hass.async_add_job(
        BME280, bus, i2c_address,
        config.get(CONF_OVERSAMPLING_TEMP),
        config.get(CONF_OVERSAMPLING_PRES),
        config.get(CONF_OVERSAMPLING_HUM),
        config.get(CONF_OPERATION_MODE),
        config.get(CONF_T_STANDBY),
        config.get(CONF_FILTER_MODE),
        config.get(CONF_DELTA_TEMP)
    )
    if not sensor.sample_ok:
        _LOGGER.error("BME280 sensor not detected at %s", i2c_address)
        return False

    dev = []
    try:
        for variable in config[CONF_MONITORED_CONDITIONS]:
            dev.append(BME280Sensor(
                sensor, variable, SENSOR_TYPES[variable][1], name))
    except KeyError:
        pass

    async_add_devices(dev)


class BME280:
    """BME280 sensor working in i2C bus."""

    def __init__(self, bus,
                 i2c_address=DEFAULT_I2C_ADDRESS,
                 osrs_t=DEFAULT_OVERSAMPLING_TEMP,
                 osrs_p=DEFAULT_OVERSAMPLING_PRES,
                 osrs_h=DEFAULT_OVERSAMPLING_HUM,
                 mode=DEFAULT_OPERATION_MODE,
                 t_sb=DEFAULT_T_STANDBY,
                 filter_mode=DEFAULT_FILTER_MODE,
                 delta_temp=DEFAULT_DELTA_TEMP,
                 spi3w_en=0):  # 3-wire SPI Disable):
        """Initialize the sensor handler."""
        # Sensor location
        self._bus = bus
        self._i2c_add = int(i2c_address, 0)

        # BME280 parameters
        self.mode = mode
        self.ctrl_meas_reg = (osrs_t << 5) | (osrs_p << 2) | self.mode
        self.config_reg = (t_sb << 5) | (filter_mode << 2) | spi3w_en
        self.ctrl_hum_reg = osrs_h

        self._delta_temp = delta_temp
        self._with_pressure = osrs_p > 0
        self._with_humidity = osrs_h > 0

        # Calibration data
        self._calibration_t = None
        self._calibration_h = None
        self._calibration_p = None
        self._temp_fine = None

        # Sensor data
        self._ok = False
        self._temperature = None
        self._humidity = None
        self._pressure = None

        self.update(True)

    def _compensate_temperature(self, adc_t):
        """Compensate temperature.

        Formula from datasheet Bosch BME280 Environmental sensor.
        8.1 Compensation formulas in double precision floating point
        Edition BST-BME280-DS001-10 | Revision 1.1 | May 2015
        """
        var_1 = ((adc_t / 16384.0 - self._calibration_t[0] / 1024.0)
                 * self._calibration_t[1])
        var_2 = ((adc_t / 131072.0 - self._calibration_t[0] / 8192.0)
                 * (adc_t / 131072.0 - self._calibration_t[0] / 8192.0)
                 * self._calibration_t[2])
        self._temp_fine = var_1 + var_2
        if self._delta_temp != 0.:  # temperature correction for self heating
            temp = self._temp_fine / 5120.0 + self._delta_temp
            self._temp_fine = temp * 5120.0
        else:
            temp = self._temp_fine / 5120.0
        return temp

    def _compensate_pressure(self, adc_p):
        """Compensate pressure.

        Formula from datasheet Bosch BME280 Environmental sensor.
        8.1 Compensation formulas in double precision floating point
        Edition BST-BME280-DS001-10 | Revision 1.1 | May 2015.
        """
        var_1 = (self._temp_fine / 2.0) - 64000.0
        var_2 = ((var_1 / 4.0) * (var_1 / 4.0)) / 2048
        var_2 *= self._calibration_p[5]
        var_2 += ((var_1 * self._calibration_p[4]) * 2.0)
        var_2 = (var_2 / 4.0) + (self._calibration_p[3] * 65536.0)
        var_1 = (((self._calibration_p[2]
                   * (((var_1 / 4.0) * (var_1 / 4.0)) / 8192)) / 8)
                 + ((self._calibration_p[1] * var_1) / 2.0))
        var_1 /= 262144
        var_1 = ((32768 + var_1) * self._calibration_p[0]) / 32768

        if var_1 == 0:
            return 0

        pressure = ((1048576 - adc_p) - (var_2 / 4096)) * 3125
        if pressure < 0x80000000:
            pressure = (pressure * 2.0) / var_1
        else:
            pressure = (pressure / var_1) * 2

        var_1 = (self._calibration_p[8]
                 * (((pressure / 8.0) * (pressure / 8.0)) / 8192.0)) / 4096
        var_2 = ((pressure / 4.0) * self._calibration_p[7]) / 8192.0
        pressure += ((var_1 + var_2 + self._calibration_p[6]) / 16.0)

        return pressure / 100

    def _compensate_humidity(self, adc_h):
        """Compensate humidity.

        Formula from datasheet Bosch BME280 Environmental sensor.
        8.1 Compensation formulas in double precision floating point
        Edition BST-BME280-DS001-10 | Revision 1.1 | May 2015.
        """
        var_h = self._temp_fine - 76800.0
        if var_h == 0:
            return 0

        var_h = ((adc_h - (self._calibration_h[3] * 64.0 +
                           self._calibration_h[4] / 16384.0 * var_h))
                 * (self._calibration_h[1] / 65536.0
                    * (1.0 + self._calibration_h[5] / 67108864.0 * var_h
                       * (1.0 + self._calibration_h[2] / 67108864.0 * var_h))))
        var_h *= 1.0 - self._calibration_h[0] * var_h / 524288.0

        if var_h > 100.0:
            var_h = 100.0
        elif var_h < 0.0:
            var_h = 0.0

        return var_h

    def _populate_calibration_data(self):
        """Populate calibration data.

        From datasheet Bosch BME280 Environmental sensor.
        """
        calibration_t = []
        calibration_p = []
        calibration_h = []
        raw_data = []

        try:
            for i in range(0x88, 0x88 + 24):
                raw_data.append(self._bus.read_byte_data(self._i2c_add, i))
            raw_data.append(self._bus.read_byte_data(self._i2c_add, 0xA1))
            for i in range(0xE1, 0xE1 + 7):
                raw_data.append(self._bus.read_byte_data(self._i2c_add, i))
        except OSError as exc:
            _LOGGER.error("Can't populate calibration data: %s", exc)
            return

        calibration_t.append((raw_data[1] << 8) | raw_data[0])
        calibration_t.append((raw_data[3] << 8) | raw_data[2])
        calibration_t.append((raw_data[5] << 8) | raw_data[4])

        if self._with_pressure:
            calibration_p.append((raw_data[7] << 8) | raw_data[6])
            calibration_p.append((raw_data[9] << 8) | raw_data[8])
            calibration_p.append((raw_data[11] << 8) | raw_data[10])
            calibration_p.append((raw_data[13] << 8) | raw_data[12])
            calibration_p.append((raw_data[15] << 8) | raw_data[14])
            calibration_p.append((raw_data[17] << 8) | raw_data[16])
            calibration_p.append((raw_data[19] << 8) | raw_data[18])
            calibration_p.append((raw_data[21] << 8) | raw_data[20])
            calibration_p.append((raw_data[23] << 8) | raw_data[22])

        if self._with_humidity:
            calibration_h.append(raw_data[24])
            calibration_h.append((raw_data[26] << 8) | raw_data[25])
            calibration_h.append(raw_data[27])
            calibration_h.append((raw_data[28] << 4) | (0x0F & raw_data[29]))
            calibration_h.append(
                (raw_data[30] << 4) | ((raw_data[29] >> 4) & 0x0F))
            calibration_h.append(raw_data[31])

        for i in range(1, 2):
            if calibration_t[i] & 0x8000:
                calibration_t[i] = (-calibration_t[i] ^ 0xFFFF) + 1

        if self._with_pressure:
            for i in range(1, 8):
                if calibration_p[i] & 0x8000:
                    calibration_p[i] = (-calibration_p[i] ^ 0xFFFF) + 1

        if self._with_humidity:
            for i in range(0, 6):
                if calibration_h[i] & 0x8000:
                    calibration_h[i] = (-calibration_h[i] ^ 0xFFFF) + 1

        self._calibration_t = calibration_t
        self._calibration_h = calibration_h
        self._calibration_p = calibration_p

    def _take_forced_measurement(self):
        """Take a forced measurement.

        In forced mode, the BME sensor goes back to sleep after each
        measurement and we need to set it to forced mode once at this point,
        so it will take the next measurement and then return to sleep again.
        In normal mode simply does new measurements periodically.
        """
        # set to forced mode, i.e. "take next measurement"
        self._bus.write_byte_data(self._i2c_add, 0xF4, self.ctrl_meas_reg)
        while self._bus.read_byte_data(self._i2c_add, 0xF3) & 0x08:
            asyncio.sleep(0.005)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self, first_reading=False):
        """Read raw data and update compensated variables."""
        try:
            if first_reading or not self._ok:
                self._bus.write_byte_data(self._i2c_add, 0xF2,
                                          self.ctrl_hum_reg)
                self._bus.write_byte_data(self._i2c_add, 0xF5, self.config_reg)
                self._bus.write_byte_data(self._i2c_add, 0xF4,
                                          self.ctrl_meas_reg)
                self._populate_calibration_data()

            if self.mode == 2:  # MODE_FORCED
                self._take_forced_measurement()

            data = []
            for i in range(0xF7, 0xF7 + 8):
                data.append(self._bus.read_byte_data(self._i2c_add, i))
        except OSError as exc:
            _LOGGER.warning("Bad update: %s", exc)
            return

        pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
        temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
        hum_raw = (data[6] << 8) | data[7]

        self._ok = False
        temperature = self._compensate_temperature(temp_raw)
        if (temperature >= -20) and (temperature < 80):
            self._temperature = temperature
            self._ok = True
        if self._with_humidity:
            humidity = self._compensate_humidity(hum_raw)
            if (humidity >= 0) and (humidity <= 100):
                self._humidity = humidity
            else:
                self._ok = False
        if self._with_pressure:
            pressure = self._compensate_pressure(pres_raw)
            if pressure > 100:
                self._pressure = pressure
            else:
                self._ok = False

    @property
    def sample_ok(self):
        """Return sensor ok state."""
        return self._ok

    @property
    def temperature(self):
        """Return temperature in celsius."""
        return self._temperature

    @property
    def humidity(self):
        """Return relative humidity in percentage."""
        return self._humidity

    @property
    def pressure(self):
        """Return pressure in hPa."""
        return self._pressure


class BME280Sensor(Entity):
    """Implementation of the BME280 sensor."""

    def __init__(self, bme280_client, sensor_type, temp_unit, name):
        """Initialize the sensor."""
        self.client_name = name
        self._name = SENSOR_TYPES[sensor_type][0]
        self.bme280_client = bme280_client
        self.temp_unit = temp_unit
        self.type = sensor_type
        self._state = None
        self._unit_of_measurement = SENSOR_TYPES[sensor_type][1]

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self.client_name, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._unit_of_measurement

    @asyncio.coroutine
    def async_update(self):
        """Get the latest data from the BME280 and update the states."""
        yield from self.hass.async_add_job(self.bme280_client.update)
        if self.bme280_client.sample_ok:
            if self.type == SENSOR_TEMP:
                temperature = round(self.bme280_client.temperature, 2)
                if self.temp_unit == TEMP_FAHRENHEIT:
                    temperature = round(celsius_to_fahrenheit(temperature), 1)
                self._state = temperature
            elif self.type == SENSOR_HUMID:
                self._state = round(self.bme280_client.humidity, 2)
            elif self.type == SENSOR_PRESS:
                self._state = round(self.bme280_client.pressure, 2)
        else:
            _LOGGER.warning("Bad update of sensor.%s", self.name)

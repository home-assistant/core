"""Support for EnOcean sensors."""
import logging

import voluptuous as vol

from homeassistant.components import enocean
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_DEVICE_CLASS, CONF_ID, CONF_NAME, DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE, TEMP_CELSIUS, POWER_WATT)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_MAX_TEMP = 'max_temp'
CONF_MIN_TEMP = 'min_temp'
CONF_RANGE_FROM = 'range_from'
CONF_RANGE_TO = 'range_to'

DEFAULT_NAME = 'EnOcean sensor'

DEVICE_CLASS_POWER = 'powersensor'

SENSOR_TYPES = {
    DEVICE_CLASS_HUMIDITY: {
        'name': 'Humidity',
        'unit': '%',
        'icon': 'mdi:water-percent',
        'class': DEVICE_CLASS_HUMIDITY,
    },
    DEVICE_CLASS_POWER: {
        'name': 'Power',
        'unit': POWER_WATT,
        'icon': 'mdi:power-plug',
        'class': DEVICE_CLASS_POWER,
    },
    DEVICE_CLASS_TEMPERATURE: {
        'name': 'Temperature',
        'unit': TEMP_CELSIUS,
        'icon': 'mdi:thermometer',
        'class': DEVICE_CLASS_TEMPERATURE,
    },
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ID): vol.All(cv.ensure_list, [vol.Coerce(int)]),
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_DEVICE_CLASS, default=DEVICE_CLASS_POWER): cv.string,
    vol.Optional(CONF_MAX_TEMP, default=40): vol.Coerce(int),
    vol.Optional(CONF_MIN_TEMP, default=0): vol.Coerce(int),
    vol.Optional(CONF_RANGE_FROM, default=255): cv.positive_int,
    vol.Optional(CONF_RANGE_TO, default=0): cv.positive_int,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up an EnOcean sensor device."""
    dev_id = config.get(CONF_ID)
    dev_name = config.get(CONF_NAME)
    dev_class = config.get(CONF_DEVICE_CLASS)

    if dev_class == DEVICE_CLASS_TEMPERATURE:
        temp_min = config.get(CONF_MIN_TEMP)
        temp_max = config.get(CONF_MAX_TEMP)
        range_from = config.get(CONF_RANGE_FROM)
        range_to = config.get(CONF_RANGE_TO)
        add_entities([EnOceanTemperatureSensor(
            dev_id, dev_name, temp_min, temp_max, range_from, range_to)])

    elif dev_class == DEVICE_CLASS_HUMIDITY:
        add_entities([EnOceanHumiditySensor(dev_id, dev_name)])

    elif dev_class == DEVICE_CLASS_POWER:
        add_entities([EnOceanPowerSensor(dev_id, dev_name)])


class EnOceanSensor(enocean.EnOceanDevice):
    """Representation of an  EnOcean sensor device such as a power meter."""

    def __init__(self, dev_id, dev_name, sensor_type):
        """Initialize the EnOcean sensor device."""
        super().__init__(dev_id, dev_name)
        self._sensor_type = sensor_type
        self._device_class = SENSOR_TYPES[self._sensor_type]['class']
        self._dev_name = '{} {}'.format(
            SENSOR_TYPES[self._sensor_type]['name'], dev_name)
        self._unit_of_measurement = SENSOR_TYPES[self._sensor_type]['unit']
        self._icon = SENSOR_TYPES[self._sensor_type]['icon']
        self._state = None

    @property
    def name(self):
        """Return the name of the device."""
        return self._dev_name

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return self._icon

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    def value_changed(self, packet):
        """Update the internal state of the sensor."""


class EnOceanPowerSensor(EnOceanSensor):
    """Representation of an EnOcean power sensor.

    EEPs (EnOcean Equipment Profiles):
    - A5-12-01 (Automated Meter Reading, Electricity)
    """

    def __init__(self, dev_id, dev_name):
        """Initialize the EnOcean power sensor device."""
        super().__init__(dev_id, dev_name, DEVICE_CLASS_POWER)

    def value_changed(self, packet):
        """Update the internal state of the sensor."""
        if packet.rorg != 0xA5:
            return
        packet.parse_eep(0x12, 0x01)
        if packet.parsed['DT']['raw_value'] == 1:
            # this packet reports the current value
            raw_val = packet.parsed['MR']['raw_value']
            divisor = packet.parsed['DIV']['raw_value']
            self._state = raw_val / (10 ** divisor)
            self.schedule_update_ha_state()


class EnOceanTemperatureSensor(EnOceanSensor):
    """Representation of an EnOcean temperature sensor device.

    EEPs (EnOcean Equipment Profiles):
    - A5-02-01 to A5-02-1B All 8 Bit Temperature Sensors of A5-02
    - A5-10-01 to A5-10-14 (Room Operating Panels)
    - A5-04-01 (Temp. and Humidity Sensor, Range 0°C to +40°C and 0% to 100%)
    - A5-04-02 (Temp. and Humidity Sensor, Range -20°C to +60°C and 0% to 100%)
    - A5-10-10 (Temp. and Humidity Sensor and Set Point)
    - A5-10-12 (Temp. and Humidity Sensor, Set Point and Occupancy Control)
    - 10 Bit Temp. Sensors are not supported (A5-02-20, A5-02-30)

    For the following EEPs the scales must be set to "0 to 250":
    - A5-04-01
    - A5-04-02
    - A5-10-10 to A5-10-14
    """

    def __init__(self, dev_id, dev_name, scale_min, scale_max,
                 range_from, range_to):
        """Initialize the EnOcean temperature sensor device."""
        super().__init__(dev_id, dev_name, DEVICE_CLASS_TEMPERATURE)
        self._scale_min = scale_min
        self._scale_max = scale_max
        self.range_from = range_from
        self.range_to = range_to

    def value_changed(self, packet):
        """Update the internal state of the sensor."""
        if packet.data[0] != 0xa5:
            return
        temp_scale = self._scale_max - self._scale_min
        temp_range = self.range_to - self.range_from
        raw_val = packet.data[3]
        temperature = temp_scale / temp_range * (raw_val - self.range_from)
        temperature += self._scale_min
        self._state = round(temperature, 1)
        self.schedule_update_ha_state()


class EnOceanHumiditySensor(EnOceanSensor):
    """Representation of an EnOcean humidity sensor device.

    EEPs (EnOcean Equipment Profiles):
    - A5-04-01 (Temp. and Humidity Sensor, Range 0°C to +40°C and 0% to 100%)
    - A5-04-02 (Temp. and Humidity Sensor, Range -20°C to +60°C and 0% to 100%)
    - A5-10-10 to A5-10-14 (Room Operating Panels)
    """

    def __init__(self, dev_id, dev_name):
        """Initialize the EnOcean humidity sensor device."""
        super().__init__(dev_id, dev_name, DEVICE_CLASS_HUMIDITY)

    def value_changed(self, packet):
        """Update the internal state of the sensor."""
        if packet.rorg != 0xA5:
            return
        humidity = packet.data[2] * 100 / 250
        self._state = round(humidity, 1)
        self.schedule_update_ha_state()

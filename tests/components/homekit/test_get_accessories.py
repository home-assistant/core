"""Package to test the get_accessory method."""
import logging
import unittest
from unittest.mock import patch, Mock

from homeassistant.core import State
from homeassistant.components.cover import (
    SUPPORT_OPEN, SUPPORT_CLOSE)
from homeassistant.components.climate import (
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.components.homekit import get_accessory, TYPES
from homeassistant.const import (
    ATTR_CODE, ATTR_UNIT_OF_MEASUREMENT, ATTR_SUPPORTED_FEATURES,
    TEMP_CELSIUS, TEMP_FAHRENHEIT, ATTR_DEVICE_CLASS)

_LOGGER = logging.getLogger(__name__)

CONFIG = {}


def test_get_accessory_invalid_aid(caplog):
    """Test with unsupported component."""
    assert get_accessory(None, State('light.demo', 'on'),
                         None, config=None) is None
    assert caplog.records[0].levelname == 'WARNING'
    assert 'invalid aid' in caplog.records[0].msg


def test_not_supported():
    """Test if none is returned if entity isn't supported."""
    assert get_accessory(None, State('demo.demo', 'on'), 2, config=None) \
        is None


class TestGetAccessories(unittest.TestCase):
    """Methods to test the get_accessory method."""

    def setUp(self):
        """Setup Mock type."""
        self.mock_type = Mock()

    def tearDown(self):
        """Test if mock type was called."""
        self.assertTrue(self.mock_type.called)

    def test_sensor_temperature(self):
        """Test temperature sensor with device class temperature."""
        with patch.dict(TYPES, {'TemperatureSensor': self.mock_type}):
            state = State('sensor.temperature', '23',
                          {ATTR_DEVICE_CLASS: 'temperature'})
            get_accessory(None, state, 2, {})

    def test_sensor_temperature_celsius(self):
        """Test temperature sensor with Celsius as unit."""
        with patch.dict(TYPES, {'TemperatureSensor': self.mock_type}):
            state = State('sensor.temperature', '23',
                          {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
            get_accessory(None, state, 2, {})

    def test_sensor_temperature_fahrenheit(self):
        """Test temperature sensor with Fahrenheit as unit."""
        with patch.dict(TYPES, {'TemperatureSensor': self.mock_type}):
            state = State('sensor.temperature', '74',
                          {ATTR_UNIT_OF_MEASUREMENT: TEMP_FAHRENHEIT})
            get_accessory(None, state, 2, {})

    def test_sensor_humidity(self):
        """Test humidity sensor with device class humidity."""
        with patch.dict(TYPES, {'HumiditySensor': self.mock_type}):
            state = State('sensor.humidity', '20',
                          {ATTR_DEVICE_CLASS: 'humidity'})
            get_accessory(None, state, 2, {})

    def test_sensor_humidity_unit(self):
        """Test humidity sensor with % as unit."""
        with patch.dict(TYPES, {'HumiditySensor': self.mock_type}):
            state = State('sensor.humidity', '20',
                          {ATTR_UNIT_OF_MEASUREMENT: '%'})
            get_accessory(None, state, 2, {})

    def test_air_quality_sensor(self):
        """Test air quality sensor with pm25 class."""
        with patch.dict(TYPES, {'AirQualitySensor': self.mock_type}):
            state = State('sensor.air_quality', '40',
                          {ATTR_DEVICE_CLASS: 'pm25'})
            get_accessory(None, state, 2, {})

    def test_air_quality_sensor_entity_id(self):
        """Test air quality sensor with entity_id contains pm25."""
        with patch.dict(TYPES, {'AirQualitySensor': self.mock_type}):
            state = State('sensor.air_quality_pm25', '40', {})
            get_accessory(None, state, 2, {})

    def test_co2_sensor(self):
        """Test co2 sensor with device class co2."""
        with patch.dict(TYPES, {'CarbonDioxideSensor': self.mock_type}):
            state = State('sensor.airmeter', '500',
                          {ATTR_DEVICE_CLASS: 'co2'})
            get_accessory(None, state, 2, {})

    def test_co2_sensor_entity_id(self):
        """Test co2 sensor with entity_id contains co2."""
        with patch.dict(TYPES, {'CarbonDioxideSensor': self.mock_type}):
            state = State('sensor.airmeter_co2', '500', {})
            get_accessory(None, state, 2, {})

    def test_light_sensor(self):
        """Test light sensor with device class lux."""
        with patch.dict(TYPES, {'LightSensor': self.mock_type}):
            state = State('sensor.light', '900',
                          {ATTR_DEVICE_CLASS: 'light'})
            get_accessory(None, state, 2, {})

    def test_light_sensor_unit_lm(self):
        """Test light sensor with lm as unit."""
        with patch.dict(TYPES, {'LightSensor': self.mock_type}):
            state = State('sensor.light', '900',
                          {ATTR_UNIT_OF_MEASUREMENT: 'lm'})
            get_accessory(None, state, 2, {})

    def test_light_sensor_unit_lux(self):
        """Test light sensor with lux as unit."""
        with patch.dict(TYPES, {'LightSensor': self.mock_type}):
            state = State('sensor.light', '900',
                          {ATTR_UNIT_OF_MEASUREMENT: 'lux'})
            get_accessory(None, state, 2, {})

    def test_binary_sensor(self):
        """Test binary sensor with opening class."""
        with patch.dict(TYPES, {'BinarySensor': self.mock_type}):
            state = State('binary_sensor.opening', 'on',
                          {ATTR_DEVICE_CLASS: 'opening'})
            get_accessory(None, state, 2, {})

    def test_device_tracker(self):
        """Test binary sensor with opening class."""
        with patch.dict(TYPES, {'BinarySensor': self.mock_type}):
            state = State('device_tracker.someone', 'not_home', {})
            get_accessory(None, state, 2, {})

    def test_garage_door(self):
        """Test cover with device_class: 'garage' and required features."""
        with patch.dict(TYPES, {'GarageDoorOpener': self.mock_type}):
            state = State('cover.garage_door', 'open', {
                ATTR_DEVICE_CLASS: 'garage',
                ATTR_SUPPORTED_FEATURES:
                    SUPPORT_OPEN | SUPPORT_CLOSE})
            get_accessory(None, state, 2, {})

    def test_cover_set_position(self):
        """Test cover with support for set_cover_position."""
        with patch.dict(TYPES, {'WindowCovering': self.mock_type}):
            state = State('cover.set_position', 'open',
                          {ATTR_SUPPORTED_FEATURES: 4})
            get_accessory(None, state, 2, {})

    def test_cover_open_close(self):
        """Test cover with support for open and close."""
        with patch.dict(TYPES, {'WindowCoveringBasic': self.mock_type}):
            state = State('cover.open_window', 'open',
                          {ATTR_SUPPORTED_FEATURES: 3})
            get_accessory(None, state, 2, {})

    def test_alarm_control_panel(self):
        """Test alarm control panel."""
        config = {ATTR_CODE: '1234'}
        with patch.dict(TYPES, {'SecuritySystem': self.mock_type}):
            state = State('alarm_control_panel.test', 'armed')
            get_accessory(None, state, 2, config)

        # pylint: disable=unsubscriptable-object
        print(self.mock_type.call_args[1])
        self.assertEqual(
            self.mock_type.call_args[1]['config'][ATTR_CODE], '1234')

    def test_climate(self):
        """Test climate devices."""
        with patch.dict(TYPES, {'Thermostat': self.mock_type}):
            state = State('climate.test', 'auto')
            get_accessory(None, state, 2, {})

    def test_light(self):
        """Test light devices."""
        with patch.dict(TYPES, {'Light': self.mock_type}):
            state = State('light.test', 'on')
            get_accessory(None, state, 2, {})

    def test_climate_support_auto(self):
        """Test climate devices with support for auto mode."""
        with patch.dict(TYPES, {'Thermostat': self.mock_type}):
            state = State('climate.test', 'auto', {
                ATTR_SUPPORTED_FEATURES:
                    SUPPORT_TARGET_TEMPERATURE_LOW |
                    SUPPORT_TARGET_TEMPERATURE_HIGH})
            get_accessory(None, state, 2, {})

    def test_switch(self):
        """Test switch."""
        with patch.dict(TYPES, {'Switch': self.mock_type}):
            state = State('switch.test', 'on')
            get_accessory(None, state, 2, {})

    def test_remote(self):
        """Test remote."""
        with patch.dict(TYPES, {'Switch': self.mock_type}):
            state = State('remote.test', 'on')
            get_accessory(None, state, 2, {})

    def test_input_boolean(self):
        """Test input_boolean."""
        with patch.dict(TYPES, {'Switch': self.mock_type}):
            state = State('input_boolean.test', 'on')
            get_accessory(None, state, 2, {})

    def test_lock(self):
        """Test lock."""
        with patch.dict(TYPES, {'Lock': self.mock_type}):
            state = State('lock.test', 'locked')
            get_accessory(None, state, 2, {})

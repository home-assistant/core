"""Package to test the get_accessory method."""
import logging
import unittest
from unittest.mock import patch, Mock

from homeassistant.core import State
from homeassistant.components.climate import (
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.components.homekit import get_accessory, TYPES
from homeassistant.const import (
    ATTR_CODE, ATTR_UNIT_OF_MEASUREMENT, ATTR_SUPPORTED_FEATURES,
    TEMP_CELSIUS, TEMP_FAHRENHEIT)

_LOGGER = logging.getLogger(__name__)

CONFIG = {}


def test_get_accessory_invalid_aid(caplog):
    """Test with unsupported component."""
    assert get_accessory(None, State('light.demo', 'on'),
                         aid=None, config=None) is None
    assert caplog.records[0].levelname == 'WARNING'
    assert 'invalid aid' in caplog.records[0].msg


def test_not_supported():
    """Test if none is returned if entity isn't supported."""
    assert get_accessory(None, State('demo.demo', 'on'), aid=2, config=None) \
        is None


class TestGetAccessories(unittest.TestCase):
    """Methods to test the get_accessory method."""

    def setUp(self):
        """Setup Mock type."""
        self.mock_type = Mock()

    def tearDown(self):
        """Test if mock type was called."""
        self.assertTrue(self.mock_type.called)

    def test_sensor_temperature_celsius(self):
        """Test temperature sensor with Celsius as unit."""
        with patch.dict(TYPES, {'TemperatureSensor': self.mock_type}):
            state = State('sensor.temperature', '23',
                          {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS})
            get_accessory(None, state, 2, {})

    # pylint: disable=invalid-name
    def test_sensor_temperature_fahrenheit(self):
        """Test temperature sensor with Fahrenheit as unit."""
        with patch.dict(TYPES, {'TemperatureSensor': self.mock_type}):
            state = State('sensor.temperature', '74',
                          {ATTR_UNIT_OF_MEASUREMENT: TEMP_FAHRENHEIT})
            get_accessory(None, state, 2, {})

    def test_sensor_humidity(self):
        """Test humidity sensor with % as unit."""
        with patch.dict(TYPES, {'HumiditySensor': self.mock_type}):
            state = State('sensor.humidity', '20',
                          {ATTR_UNIT_OF_MEASUREMENT: '%'})
            get_accessory(None, state, 2, {})

    def test_cover_set_position(self):
        """Test cover with support for set_cover_position."""
        with patch.dict(TYPES, {'WindowCovering': self.mock_type}):
            state = State('cover.set_position', 'open',
                          {ATTR_SUPPORTED_FEATURES: 4})
            get_accessory(None, state, 2, {})

    def test_alarm_control_panel(self):
        """Test alarm control panel."""
        config = {ATTR_CODE: '1234'}
        with patch.dict(TYPES, {'SecuritySystem': self.mock_type}):
            state = State('alarm_control_panel.test', 'armed')
            get_accessory(None, state, 2, config)

        # pylint: disable=unsubscriptable-object
        self.assertEqual(
            self.mock_type.call_args[1].get('alarm_code'), '1234')

    def test_climate(self):
        """Test climate devices."""
        with patch.dict(TYPES, {'Thermostat': self.mock_type}):
            state = State('climate.test', 'auto')
            get_accessory(None, state, 2, {})

        # pylint: disable=unsubscriptable-object
        self.assertEqual(
            self.mock_type.call_args[0][-1], False)  # support_auto

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

        # pylint: disable=unsubscriptable-object
        self.assertEqual(
            self.mock_type.call_args[0][-1], True)  # support_auto

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

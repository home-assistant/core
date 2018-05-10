"""Package to test the get_accessory method."""
import logging
from unittest.mock import patch, Mock

import pytest

from homeassistant.core import State
from homeassistant.components.cover import SUPPORT_OPEN, SUPPORT_CLOSE
from homeassistant.components.climate import (
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.components.homekit import get_accessory, TYPES
from homeassistant.const import (
    ATTR_CODE, ATTR_DEVICE_CLASS, ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT, TEMP_CELSIUS, TEMP_FAHRENHEIT)

_LOGGER = logging.getLogger(__name__)


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


@pytest.mark.parametrize('type_name, entity_id, state, attrs, config', [
    ('Light', 'light.test', 'on', {}, None),
    ('Lock', 'lock.test', 'locked', {}, None),

    ('Thermostat', 'climate.test', 'auto', {}, None),
    ('Thermostat', 'climate.test', 'auto',
     {ATTR_SUPPORTED_FEATURES: SUPPORT_TARGET_TEMPERATURE_LOW |
      SUPPORT_TARGET_TEMPERATURE_HIGH}, None),

    ('SecuritySystem', 'alarm_control_panel.test', 'armed', {},
     {ATTR_CODE: '1234'}),
])
def test_types(type_name, entity_id, state, attrs, config):
    """Test if types are associated correctly."""
    mock_type = Mock()
    with patch.dict(TYPES, {type_name: mock_type}):
        entity_state = State(entity_id, state, attrs)
        get_accessory(None, entity_state, 2, config)
    assert mock_type.called

    if config:
        assert mock_type.call_args[1]['config'] == config


@pytest.mark.parametrize('type_name, entity_id, state, attrs', [
    ('GarageDoorOpener', 'cover.garage_door', 'open',
     {ATTR_DEVICE_CLASS: 'garage',
      ATTR_SUPPORTED_FEATURES: SUPPORT_OPEN | SUPPORT_CLOSE}),
    ('WindowCovering', 'cover.set_position', 'open',
     {ATTR_SUPPORTED_FEATURES: 4}),
    ('WindowCoveringBasic', 'cover.open_window', 'open',
     {ATTR_SUPPORTED_FEATURES: 3}),
])
def test_type_covers(type_name, entity_id, state, attrs):
    """Test if cover types are associated correctly."""
    mock_type = Mock()
    with patch.dict(TYPES, {type_name: mock_type}):
        entity_state = State(entity_id, state, attrs)
        get_accessory(None, entity_state, 2, None)
    assert mock_type.called


@pytest.mark.parametrize('type_name, entity_id, state, attrs', [
    ('BinarySensor', 'binary_sensor.opening', 'on',
     {ATTR_DEVICE_CLASS: 'opening'}),
    ('BinarySensor', 'device_tracker.someone', 'not_home', {}),

    ('AirQualitySensor', 'sensor.air_quality_pm25', '40', {}),
    ('AirQualitySensor', 'sensor.air_quality', '40',
     {ATTR_DEVICE_CLASS: 'pm25'}),

    ('CarbonDioxideSensor', 'sensor.airmeter_co2', '500', {}),
    ('CarbonDioxideSensor', 'sensor.airmeter', '500',
     {ATTR_DEVICE_CLASS: 'co2'}),

    ('HumiditySensor', 'sensor.humidity', '20',
     {ATTR_DEVICE_CLASS: 'humidity', ATTR_UNIT_OF_MEASUREMENT: '%'}),

    ('LightSensor', 'sensor.light', '900', {ATTR_DEVICE_CLASS: 'illuminance'}),
    ('LightSensor', 'sensor.light', '900', {ATTR_UNIT_OF_MEASUREMENT: 'lm'}),
    ('LightSensor', 'sensor.light', '900', {ATTR_UNIT_OF_MEASUREMENT: 'lx'}),

    ('TemperatureSensor', 'sensor.temperature', '23',
     {ATTR_DEVICE_CLASS: 'temperature'}),
    ('TemperatureSensor', 'sensor.temperature', '23',
     {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS}),
    ('TemperatureSensor', 'sensor.temperature', '74',
     {ATTR_UNIT_OF_MEASUREMENT: TEMP_FAHRENHEIT}),
])
def test_type_sensors(type_name, entity_id, state, attrs):
    """Test if sensor types are associated correctly."""
    mock_type = Mock()
    with patch.dict(TYPES, {type_name: mock_type}):
        entity_state = State(entity_id, state, attrs)
        get_accessory(None, entity_state, 2, None)
    assert mock_type.called


@pytest.mark.parametrize('type_name, entity_id, state, attrs', [
    ('Switch', 'switch.test', 'on', {}),
    ('Switch', 'remote.test', 'on', {}),
    ('Switch', 'input_boolean.test', 'on', {}),
])
def test_type_switches(type_name, entity_id, state, attrs):
    """Test if switch types are associated correctly."""
    mock_type = Mock()
    with patch.dict(TYPES, {type_name: mock_type}):
        entity_state = State(entity_id, state, attrs)
        get_accessory(None, entity_state, 2, None)
    assert mock_type.called

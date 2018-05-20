"""Package to test the get_accessory method."""
from unittest.mock import patch, Mock

import pytest

from homeassistant.core import State
from homeassistant.components.cover import SUPPORT_CLOSE, SUPPORT_OPEN
from homeassistant.components.climate import (
    SUPPORT_TARGET_TEMPERATURE_HIGH, SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.components.homekit import get_accessory, TYPES
from homeassistant.const import (
    ATTR_CODE, ATTR_DEVICE_CLASS, ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT, CONF_NAME, TEMP_CELSIUS, TEMP_FAHRENHEIT)


def test_not_supported(caplog):
    """Test if none is returned if entity isn't supported."""
    # not supported entity
    assert get_accessory(None, State('demo.demo', 'on'), 2, {}) is None

    # invalid aid
    assert get_accessory(None, State('light.demo', 'on'), None, None) is None
    assert caplog.records[0].levelname == 'WARNING'
    assert 'invalid aid' in caplog.records[0].msg


@pytest.mark.parametrize('config, name', [
    ({CONF_NAME: 'Customize Name'}, 'Customize Name'),
])
def test_customize_options(config, name):
    """Test with customized options."""
    mock_type = Mock()
    with patch.dict(TYPES, {'Light': mock_type}):
        entity_state = State('light.demo', 'on')
        get_accessory(None, entity_state, 2, config)
    mock_type.assert_called_with(None, name, 'light.demo', 2, config)


@pytest.mark.parametrize('type_name, entity_id, state, attrs, config', [
    ('Fan', 'fan.test', 'on', {}, {}),
    ('Light', 'light.test', 'on', {}, {}),
    ('Lock', 'lock.test', 'locked', {}, {ATTR_CODE: '1234'}),
    ('SecuritySystem', 'alarm_control_panel.test', 'armed', {},
     {ATTR_CODE: '1234'}),
    ('Thermostat', 'climate.test', 'auto', {}, {}),
    ('Thermostat', 'climate.test', 'auto',
     {ATTR_SUPPORTED_FEATURES: SUPPORT_TARGET_TEMPERATURE_LOW |
      SUPPORT_TARGET_TEMPERATURE_HIGH}, {}),
])
def test_types(type_name, entity_id, state, attrs, config):
    """Test if types are associated correctly."""
    mock_type = Mock()
    with patch.dict(TYPES, {type_name: mock_type}):
        entity_state = State(entity_id, state, attrs)
        get_accessory(None, entity_state, 2, config)
    assert mock_type.called

    if config:
        assert mock_type.call_args[0][-1] == config


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
        get_accessory(None, entity_state, 2, {})
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
        get_accessory(None, entity_state, 2, {})
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
        get_accessory(None, entity_state, 2, {})
    assert mock_type.called

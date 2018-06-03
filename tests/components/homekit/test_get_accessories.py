"""Package to test the get_accessory method."""
from unittest.mock import patch, Mock

import pytest

from homeassistant.core import State
import homeassistant.components.cover as cover
import homeassistant.components.climate as climate
import homeassistant.components.media_player as media_player
from homeassistant.components.homekit import get_accessory, TYPES
from homeassistant.components.homekit.const import (
    ACC_AIR_QUALITY_SENSOR, ACC_BINARY_SENSOR, ACC_CARBON_DIOXIDE_SENSOR,
    ACC_FAN, ACC_GARAGE_DOOR_OPENER, ACC_HUMIDITY_SENSOR, ACC_LIGHT,
    ACC_LIGHT_SENSOR, ACC_LOCK, ACC_MEDIA_PLAYER, ACC_OUTLET,
    ACC_SECURITY_SYSTEM, ACC_SWITCH, ACC_TEMPERATURE_SENSOR, ACC_THERMOSTAT,
    ACC_WINDOW_COVERING, ACC_WINDOW_COVERING_BASIC, CONF_FEATURE_LIST,
    FEATURE_ON_OFF, TYPE_OUTLET, TYPE_SWITCH)
from homeassistant.const import (
    ATTR_CODE, ATTR_DEVICE_CLASS, ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT, CONF_NAME, CONF_TYPE, STATE_ALARM_DISARMED,
    STATE_HOME, STATE_LOCKED, STATE_OFF, STATE_OPEN, TEMP_CELSIUS,
    TEMP_FAHRENHEIT)


def test_not_supported(caplog):
    """Test if none is returned if entity isn't supported."""
    # not supported entity
    assert get_accessory(None, None, State('demo.demo', STATE_OFF), 2, {}) \
        is None

    # invalid aid
    assert get_accessory(None, None, State('light.demo', STATE_OFF), None,
                         None) is None
    assert caplog.records[0].levelname == 'WARNING'
    assert 'invalid aid' in caplog.records[0].msg


def test_not_supported_media_player():
    """Test if mode isn't supported and if no supported modes."""
    # selected mode for entity not supported
    config = {CONF_FEATURE_LIST: {FEATURE_ON_OFF: None}}
    entity_state = State('media_player.demo', STATE_OFF)
    assert get_accessory(None, None, entity_state, 2, config) is None

    # no supported modes for entity
    entity_state = State('media_player.demo', STATE_OFF)
    assert get_accessory(None, None, entity_state, 2, {}) is None


@pytest.mark.parametrize('config, name', [
    ({CONF_NAME: 'Customize Name'}, 'Customize Name'),
])
def test_customize_options(config, name):
    """Test with customized options."""
    mock_type = Mock()
    with patch.dict(TYPES, {ACC_LIGHT: mock_type}):
        entity_state = State('light.demo', STATE_OFF)
        get_accessory(None, None, entity_state, 2, config)
    mock_type.assert_called_with(None, None, name,
                                 'light.demo', 2, config)


@pytest.mark.parametrize('type_name, entity_id, state, attrs, config', [
    (ACC_FAN, 'fan.test', STATE_OFF, {}, {}),
    (ACC_LIGHT, 'light.test', STATE_OFF, {}, {}),
    (ACC_LOCK, 'lock.test', STATE_LOCKED, {}, {ATTR_CODE: '1234'}),
    (ACC_MEDIA_PLAYER, 'media_player.test', STATE_OFF,
     {ATTR_SUPPORTED_FEATURES: media_player.SUPPORT_TURN_ON |
      media_player.SUPPORT_TURN_OFF}, {CONF_FEATURE_LIST:
                                       {FEATURE_ON_OFF: None}}),
    (ACC_SECURITY_SYSTEM, 'alarm_control_panel.test', STATE_ALARM_DISARMED, {},
     {ATTR_CODE: '1234'}),
    (ACC_THERMOSTAT, 'climate.test', STATE_OFF, {}, {}),
    (ACC_THERMOSTAT, 'climate.test', STATE_OFF,
     {ATTR_SUPPORTED_FEATURES: climate.SUPPORT_TARGET_TEMPERATURE_LOW |
      climate.SUPPORT_TARGET_TEMPERATURE_HIGH}, {}),
])
def test_types(type_name, entity_id, state, attrs, config):
    """Test if types are associated correctly."""
    mock_type = Mock()
    with patch.dict(TYPES, {type_name: mock_type}):
        entity_state = State(entity_id, state, attrs)
        get_accessory(None, None, entity_state, 2, config)
    assert mock_type.called

    if config:
        assert mock_type.call_args[0][-1] == config


@pytest.mark.parametrize('type_name, entity_id, state, attrs', [
    (ACC_GARAGE_DOOR_OPENER, 'cover.garage_door', STATE_OPEN,
     {ATTR_DEVICE_CLASS: 'garage',
      ATTR_SUPPORTED_FEATURES: cover.SUPPORT_OPEN | cover.SUPPORT_CLOSE}),
    (ACC_WINDOW_COVERING, 'cover.set_position', STATE_OPEN,
     {ATTR_SUPPORTED_FEATURES: 4}),
    (ACC_WINDOW_COVERING_BASIC, 'cover.open_window', STATE_OPEN,
     {ATTR_SUPPORTED_FEATURES: 3}),
])
def test_type_covers(type_name, entity_id, state, attrs):
    """Test if cover types are associated correctly."""
    mock_type = Mock()
    with patch.dict(TYPES, {type_name: mock_type}):
        entity_state = State(entity_id, state, attrs)
        get_accessory(None, None, entity_state, 2, {})
    assert mock_type.called


@pytest.mark.parametrize('type_name, entity_id, state, attrs', [
    (ACC_AIR_QUALITY_SENSOR, 'sensor.air_quality_pm25', '40', {}),
    (ACC_AIR_QUALITY_SENSOR, 'sensor.air_quality', '40',
     {ATTR_DEVICE_CLASS: 'pm25'}),
    (ACC_BINARY_SENSOR, 'binary_sensor.opening', STATE_OFF,
     {ATTR_DEVICE_CLASS: 'opening'}),
    (ACC_BINARY_SENSOR, 'device_tracker.someone', STATE_HOME, {}),
    (ACC_CARBON_DIOXIDE_SENSOR, 'sensor.airmeter_co2', '500', {}),
    (ACC_CARBON_DIOXIDE_SENSOR, 'sensor.airmeter', '500',
     {ATTR_DEVICE_CLASS: 'co2'}),
    (ACC_HUMIDITY_SENSOR, 'sensor.humidity', '20',
     {ATTR_DEVICE_CLASS: 'humidity', ATTR_UNIT_OF_MEASUREMENT: '%'}),
    (ACC_LIGHT_SENSOR, 'sensor.light', '900',
     {ATTR_DEVICE_CLASS: 'illuminance'}),
    (ACC_LIGHT_SENSOR, 'sensor.light', '900',
     {ATTR_UNIT_OF_MEASUREMENT: 'lm'}),
    (ACC_LIGHT_SENSOR, 'sensor.light', '900',
     {ATTR_UNIT_OF_MEASUREMENT: 'lx'}),
    (ACC_TEMPERATURE_SENSOR, 'sensor.temperature', '23',
     {ATTR_DEVICE_CLASS: 'temperature'}),
    (ACC_TEMPERATURE_SENSOR, 'sensor.temperature', '23',
     {ATTR_UNIT_OF_MEASUREMENT: TEMP_CELSIUS}),
    (ACC_TEMPERATURE_SENSOR, 'sensor.temperature', '74',
     {ATTR_UNIT_OF_MEASUREMENT: TEMP_FAHRENHEIT}),
])
def test_type_sensors(type_name, entity_id, state, attrs):
    """Test if sensor types are associated correctly."""
    mock_type = Mock()
    with patch.dict(TYPES, {type_name: mock_type}):
        entity_state = State(entity_id, state, attrs)
        get_accessory(None, None, entity_state, 2, {})
    assert mock_type.called


@pytest.mark.parametrize('type_name, entity_id, state, attrs, config', [
    (ACC_OUTLET, 'switch.test', STATE_OFF, {}, {CONF_TYPE: TYPE_OUTLET}),
    (ACC_SWITCH, 'automation.test', STATE_OFF, {}, {}),
    (ACC_SWITCH, 'input_boolean.test', STATE_OFF, {}, {}),
    (ACC_SWITCH, 'remote.test', STATE_OFF, {}, {}),
    (ACC_SWITCH, 'script.test', STATE_OFF, {}, {}),
    (ACC_SWITCH, 'switch.test', STATE_OFF, {}, {}),
    (ACC_SWITCH, 'switch.test', STATE_OFF, {}, {CONF_TYPE: TYPE_SWITCH}),
])
def test_type_switches(type_name, entity_id, state, attrs, config):
    """Test if switch types are associated correctly."""
    mock_type = Mock()
    with patch.dict(TYPES, {type_name: mock_type}):
        entity_state = State(entity_id, state, attrs)
        get_accessory(None, None, entity_state, 2, config)
    assert mock_type.called

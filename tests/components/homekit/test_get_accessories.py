"""Package to test the get_accessory method."""
from unittest.mock import patch, Mock

import pytest

from homeassistant.core import State
import homeassistant.components.cover as cover
import homeassistant.components.climate as climate
import homeassistant.components.media_player as media_player
from homeassistant.components.homekit import get_accessory, TYPES
from homeassistant.components.homekit.const import (
    CONF_FEATURE_LIST, FEATURE_ON_OFF, TYPE_FAUCET, TYPE_OUTLET, TYPE_SHOWER,
    TYPE_SPRINKLER, TYPE_SWITCH, TYPE_VALVE)
from homeassistant.const import (
    ATTR_CODE, ATTR_DEVICE_CLASS, ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT, CONF_NAME, CONF_TYPE, TEMP_CELSIUS,
    TEMP_FAHRENHEIT)


def test_not_supported(caplog):
    """Test if none is returned if entity isn't supported."""
    # not supported entity
    assert get_accessory(None, None, State('demo.demo', 'on'), 2, {}) \
        is None

    # invalid aid
    assert get_accessory(None, None, State('light.demo', 'on'), None, None) \
        is None
    assert caplog.records[0].levelname == 'WARNING'
    assert 'invalid aid' in caplog.records[0].msg


def test_not_supported_media_player():
    """Test if mode isn't supported and if no supported modes."""
    # selected mode for entity not supported
    config = {CONF_FEATURE_LIST: {FEATURE_ON_OFF: None}}
    entity_state = State('media_player.demo', 'on')
    assert get_accessory(None, None, entity_state, 2, config) is None

    # no supported modes for entity
    entity_state = State('media_player.demo', 'on')
    assert get_accessory(None, None, entity_state, 2, {}) is None


@pytest.mark.parametrize('config, name', [
    ({CONF_NAME: 'Customize Name'}, 'Customize Name'),
])
def test_customize_options(config, name):
    """Test with customized options."""
    mock_type = Mock()
    with patch.dict(TYPES, {'Light': mock_type}):
        entity_state = State('light.demo', 'on')
        get_accessory(None, None, entity_state, 2, config)
    mock_type.assert_called_with(None, None, name,
                                 'light.demo', 2, config)


@pytest.mark.parametrize('type_name, entity_id, state, attrs, config', [
    ('Fan', 'fan.test', 'on', {}, {}),
    ('Light', 'light.test', 'on', {}, {}),
    ('Lock', 'lock.test', 'locked', {}, {ATTR_CODE: '1234'}),
    ('MediaPlayer', 'media_player.test', 'on',
     {ATTR_SUPPORTED_FEATURES: media_player.SUPPORT_TURN_ON |
      media_player.SUPPORT_TURN_OFF}, {CONF_FEATURE_LIST:
                                       {FEATURE_ON_OFF: None}}),
    ('SecuritySystem', 'alarm_control_panel.test', 'armed_away', {},
     {ATTR_CODE: '1234'}),
    ('Thermostat', 'climate.test', 'auto', {}, {}),
    ('Thermostat', 'climate.test', 'auto',
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
    ('GarageDoorOpener', 'cover.garage_door', 'open',
     {ATTR_DEVICE_CLASS: 'garage',
      ATTR_SUPPORTED_FEATURES: cover.SUPPORT_OPEN | cover.SUPPORT_CLOSE}),
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
        get_accessory(None, None, entity_state, 2, {})
    assert mock_type.called


@pytest.mark.parametrize('type_name, entity_id, state, attrs', [
    ('BinarySensor', 'binary_sensor.opening', 'on',
     {ATTR_DEVICE_CLASS: 'opening'}),
    ('BinarySensor', 'device_tracker.someone', 'not_home', {}),
    ('AirQualitySensor', 'sensor.air_quality_pm25', '40', {}),
    ('AirQualitySensor', 'sensor.air_quality', '40',
     {ATTR_DEVICE_CLASS: 'pm25'}),
    ('CarbonMonoxideSensor', 'sensor.airmeter', '2',
     {ATTR_DEVICE_CLASS: 'co'}),
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
        get_accessory(None, None, entity_state, 2, {})
    assert mock_type.called


@pytest.mark.parametrize('type_name, entity_id, state, attrs, config', [
    ('Outlet', 'switch.test', 'on', {}, {CONF_TYPE: TYPE_OUTLET}),
    ('Switch', 'automation.test', 'on', {}, {}),
    ('Switch', 'input_boolean.test', 'on', {}, {}),
    ('Switch', 'remote.test', 'on', {}, {}),
    ('Switch', 'script.test', 'on', {}, {}),
    ('Switch', 'switch.test', 'on', {}, {}),
    ('Switch', 'switch.test', 'on', {}, {CONF_TYPE: TYPE_SWITCH}),
    ('Valve', 'switch.test', 'on', {}, {CONF_TYPE: TYPE_FAUCET}),
    ('Valve', 'switch.test', 'on', {}, {CONF_TYPE: TYPE_VALVE}),
    ('Valve', 'switch.test', 'on', {}, {CONF_TYPE: TYPE_SHOWER}),
    ('Valve', 'switch.test', 'on', {}, {CONF_TYPE: TYPE_SPRINKLER}),
])
def test_type_switches(type_name, entity_id, state, attrs, config):
    """Test if switch types are associated correctly."""
    mock_type = Mock()
    with patch.dict(TYPES, {type_name: mock_type}):
        entity_state = State(entity_id, state, attrs)
        get_accessory(None, None, entity_state, 2, config)
    assert mock_type.called

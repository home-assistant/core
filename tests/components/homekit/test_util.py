"""Test HomeKit util module."""
import pytest
import voluptuous as vol

from homeassistant.components.fan import (
    SPEED_HIGH, SPEED_LOW, SPEED_MEDIUM, SPEED_OFF)
from homeassistant.components.homekit.accessories import HomeBridge
from homeassistant.components.homekit.const import HOMEKIT_NOTIFY_ID
from homeassistant.components.homekit.util import (
    show_setup_message, dismiss_setup_message, convert_to_float,
    temperature_to_homekit, temperature_to_states, density_to_air_quality,
    fan_value_to_speed, fan_speed_to_value)
from homeassistant.components.homekit.util import validate_entity_config \
    as vec
from homeassistant.components.persistent_notification import (
    DOMAIN, ATTR_NOTIFICATION_ID)
from homeassistant.const import (
    ATTR_CODE, STATE_UNKNOWN, TEMP_CELSIUS, TEMP_FAHRENHEIT, CONF_NAME)

from tests.common import async_mock_service


def test_validate_entity_config():
    """Test validate entities."""
    configs = [{'invalid_entity_id': {}}, {'demo.test': 1},
               {'demo.test': 'test'}, {'demo.test': [1, 2]},
               {'demo.test': None}, {'demo.test': {CONF_NAME: None}}]

    for conf in configs:
        with pytest.raises(vol.Invalid):
            vec(conf)

    assert vec({}) == {}
    assert vec({'demo.test': {CONF_NAME: 'Name'}}) == \
        {'demo.test': {CONF_NAME: 'Name'}}
    assert vec({'alarm_control_panel.demo': {ATTR_CODE: '1234'}}) == \
        {'alarm_control_panel.demo': {ATTR_CODE: '1234'}}


def test_convert_to_float():
    """Test convert_to_float method."""
    assert convert_to_float(12) == 12
    assert convert_to_float(12.4) == 12.4
    assert convert_to_float(STATE_UNKNOWN) is None
    assert convert_to_float(None) is None


def test_temperature_to_homekit():
    """Test temperature conversion from HA to HomeKit."""
    assert temperature_to_homekit(20.46, TEMP_CELSIUS) == 20.5
    assert temperature_to_homekit(92.1, TEMP_FAHRENHEIT) == 33.4


def test_temperature_to_states():
    """Test temperature conversion from HomeKit to HA."""
    assert temperature_to_states(20, TEMP_CELSIUS) == 20.0
    assert temperature_to_states(20.2, TEMP_FAHRENHEIT) == 68.4


def test_density_to_air_quality():
    """Test map PM2.5 density to HomeKit AirQuality level."""
    assert density_to_air_quality(0) == 1
    assert density_to_air_quality(35) == 1
    assert density_to_air_quality(35.1) == 2
    assert density_to_air_quality(75) == 2
    assert density_to_air_quality(115) == 3
    assert density_to_air_quality(150) == 4
    assert density_to_air_quality(300) == 5


def test_fan_value_to_speed():
    """Test map fan speed values from HomeKit to Home Assistant."""
    assert fan_value_to_speed(0) == SPEED_OFF
    assert fan_value_to_speed(33) == SPEED_LOW
    assert fan_value_to_speed(34) == SPEED_MEDIUM
    assert fan_value_to_speed(75) == SPEED_HIGH


def test_fan_speed_to_value():
    """Test map fan speed values from Home Assistant to Home Kit."""
    assert fan_speed_to_value(SPEED_OFF) == 0
    assert fan_speed_to_value(SPEED_LOW) == 33
    assert fan_speed_to_value(SPEED_MEDIUM) == 66
    assert fan_speed_to_value(SPEED_HIGH) == 100
    assert fan_speed_to_value('invalid') is None


async def test_show_setup_msg(hass):
    """Test show setup message as persistence notification."""
    bridge = HomeBridge(hass)

    call_create_notification = async_mock_service(hass, DOMAIN, 'create')

    await hass.async_add_job(show_setup_message, hass, bridge)
    await hass.async_block_till_done()

    assert call_create_notification
    assert call_create_notification[0].data[ATTR_NOTIFICATION_ID] == \
        HOMEKIT_NOTIFY_ID


async def test_dismiss_setup_msg(hass):
    """Test dismiss setup message."""
    call_dismiss_notification = async_mock_service(hass, DOMAIN, 'dismiss')

    await hass.async_add_job(dismiss_setup_message, hass)
    await hass.async_block_till_done()

    assert call_dismiss_notification
    assert call_dismiss_notification[0].data[ATTR_NOTIFICATION_ID] == \
        HOMEKIT_NOTIFY_ID

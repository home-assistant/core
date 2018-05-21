"""Test HomeKit util module."""
import pytest
import voluptuous as vol

from homeassistant.components.homekit.const import HOMEKIT_NOTIFY_ID
from homeassistant.components.homekit.util import (
    convert_to_float, density_to_air_quality, dismiss_setup_message,
    show_setup_message, temperature_to_homekit, temperature_to_states)
from homeassistant.components.homekit.util import validate_entity_config \
    as vec
from homeassistant.components.persistent_notification import (
    ATTR_MESSAGE, ATTR_NOTIFICATION_ID, DOMAIN)
from homeassistant.const import (
    ATTR_CODE, CONF_NAME, STATE_UNKNOWN, TEMP_CELSIUS, TEMP_FAHRENHEIT)

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

    assert vec({'alarm_control_panel.demo': {}}) == \
        {'alarm_control_panel.demo': {ATTR_CODE: None}}
    assert vec({'alarm_control_panel.demo': {ATTR_CODE: '1234'}}) == \
        {'alarm_control_panel.demo': {ATTR_CODE: '1234'}}

    assert vec({'lock.demo': {}}) == {'lock.demo': {ATTR_CODE: None}}
    assert vec({'lock.demo': {ATTR_CODE: '1234'}}) == \
        {'lock.demo': {ATTR_CODE: '1234'}}


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


async def test_show_setup_msg(hass):
    """Test show setup message as persistence notification."""
    pincode = b'123-45-678'

    call_create_notification = async_mock_service(hass, DOMAIN, 'create')

    await hass.async_add_job(show_setup_message, hass, pincode)
    await hass.async_block_till_done()

    assert call_create_notification
    assert call_create_notification[0].data[ATTR_NOTIFICATION_ID] == \
        HOMEKIT_NOTIFY_ID
    assert pincode.decode() in call_create_notification[0].data[ATTR_MESSAGE]


async def test_dismiss_setup_msg(hass):
    """Test dismiss setup message."""
    call_dismiss_notification = async_mock_service(hass, DOMAIN, 'dismiss')

    await hass.async_add_job(dismiss_setup_message, hass)
    await hass.async_block_till_done()

    assert call_dismiss_notification
    assert call_dismiss_notification[0].data[ATTR_NOTIFICATION_ID] == \
        HOMEKIT_NOTIFY_ID

"""The tests for the Xiaomi vacuum platform."""
import asyncio
from datetime import timedelta
from unittest import mock

import pytest

from homeassistant.components.vacuum import (
    ATTR_BATTERY_ICON,
    ATTR_FAN_SPEED, ATTR_FAN_SPEED_LIST, DOMAIN,
    SERVICE_LOCATE, SERVICE_RETURN_TO_BASE, SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED, SERVICE_STOP,
    SERVICE_TOGGLE, SERVICE_TURN_OFF, SERVICE_TURN_ON)
from homeassistant.components.vacuum.xiaomi import (
    ATTR_CLEANED_AREA, ATTR_CLEANING_TIME, ATTR_DO_NOT_DISTURB, ATTR_ERROR,
    CONF_HOST, CONF_NAME, CONF_TOKEN, PLATFORM,
    SERVICE_MOVE_REMOTE_CONTROL, SERVICE_MOVE_REMOTE_CONTROL_STEP,
    SERVICE_START_REMOTE_CONTROL, SERVICE_STOP_REMOTE_CONTROL)
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES, CONF_PLATFORM, STATE_OFF, STATE_ON)
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_mirobo():
    """Mock mock_mirobo."""
    mock_vacuum = mock.MagicMock()
    mock_vacuum.Vacuum().status().data = {'test': 'raw'}
    mock_vacuum.Vacuum().status().is_on = False
    mock_vacuum.Vacuum().status().fanspeed = 38
    mock_vacuum.Vacuum().status().got_error = False
    mock_vacuum.Vacuum().status().dnd = True
    mock_vacuum.Vacuum().status().battery = 82
    mock_vacuum.Vacuum().status().clean_area = 123.43218
    mock_vacuum.Vacuum().status().clean_time = timedelta(
        hours=2, minutes=35, seconds=34)
    mock_vacuum.Vacuum().status().state = 'Test Xiaomi Charging'

    with mock.patch.dict('sys.modules', {
        'mirobo': mock_vacuum,
    }):
        yield mock_vacuum


@asyncio.coroutine
def test_xiaomi_vacuum(hass, caplog, mock_mirobo):
    """Test vacuum supported features."""
    entity_name = 'test_vacuum_cleaner'
    entity_id = '{}.{}'.format(DOMAIN, entity_name)

    yield from async_setup_component(
        hass, DOMAIN,
        {DOMAIN: {CONF_PLATFORM: PLATFORM,
                  CONF_HOST: '127.0.0.1',
                  CONF_NAME: entity_name,
                  CONF_TOKEN: '12345678901234567890123456789012'}})

    assert 'Initializing with host 127.0.0.1 (token 12345...)' in caplog.text

    # Check state attributes
    state = hass.states.get(entity_id)

    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 1023
    assert state.attributes.get(ATTR_DO_NOT_DISTURB) == STATE_ON
    assert state.attributes.get(ATTR_ERROR) is None
    assert (state.attributes.get(ATTR_BATTERY_ICON)
            == 'mdi:battery-charging-80')
    assert state.attributes.get(ATTR_CLEANING_TIME) == '2:35:34'
    assert state.attributes.get(ATTR_CLEANED_AREA) == 123.43
    assert state.attributes.get(ATTR_FAN_SPEED) == 'Quiet'
    assert (state.attributes.get(ATTR_FAN_SPEED_LIST)
            == ['Quiet', 'Balanced', 'Turbo', 'Max'])

    # Call services
    yield from hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, blocking=True)
    assert str(mock_mirobo.mock_calls[-2]) == 'call.Vacuum().start()'
    assert str(mock_mirobo.mock_calls[-1]) == 'call.Vacuum().status()'

    yield from hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, blocking=True)
    assert str(mock_mirobo.mock_calls[-2]) == 'call.Vacuum().home()'
    assert str(mock_mirobo.mock_calls[-1]) == 'call.Vacuum().status()'

    yield from hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, blocking=True)
    assert str(mock_mirobo.mock_calls[-2]) == 'call.Vacuum().start()'
    assert str(mock_mirobo.mock_calls[-1]) == 'call.Vacuum().status()'

    yield from hass.services.async_call(
        DOMAIN, SERVICE_STOP, blocking=True)
    assert str(mock_mirobo.mock_calls[-2]) == 'call.Vacuum().stop()'
    assert str(mock_mirobo.mock_calls[-1]) == 'call.Vacuum().status()'

    yield from hass.services.async_call(
        DOMAIN, SERVICE_RETURN_TO_BASE, blocking=True)
    assert str(mock_mirobo.mock_calls[-2]) == 'call.Vacuum().home()'
    assert str(mock_mirobo.mock_calls[-1]) == 'call.Vacuum().status()'

    yield from hass.services.async_call(
        DOMAIN, SERVICE_LOCATE, blocking=True)
    assert str(mock_mirobo.mock_calls[-2]) == 'call.Vacuum().find()'
    assert str(mock_mirobo.mock_calls[-1]) == 'call.Vacuum().status()'

    yield from hass.services.async_call(
        DOMAIN, SERVICE_SET_FAN_SPEED, {"fan_speed": 60}, blocking=True)
    assert (str(mock_mirobo.mock_calls[-2])
            == 'call.Vacuum().set_fan_speed(60)')
    assert str(mock_mirobo.mock_calls[-1]) == 'call.Vacuum().status()'

    yield from hass.services.async_call(
        DOMAIN, SERVICE_SEND_COMMAND,
        {"command": "raw"}, blocking=True)
    assert (str(mock_mirobo.mock_calls[-2])
            == "call.Vacuum().raw_command('raw', None)")
    assert str(mock_mirobo.mock_calls[-1]) == 'call.Vacuum().status()'

    yield from hass.services.async_call(
        DOMAIN, SERVICE_SEND_COMMAND,
        {"command": "raw", "params": {"k1": 2}}, blocking=True)
    assert (str(mock_mirobo.mock_calls[-2])
            == "call.Vacuum().raw_command('raw', {'k1': 2})")
    assert str(mock_mirobo.mock_calls[-1]) == 'call.Vacuum().status()'

    yield from hass.services.async_call(
        DOMAIN, SERVICE_START_REMOTE_CONTROL, {}, blocking=True)
    assert (str(mock_mirobo.mock_calls[-2])
            == "call.Vacuum().manual_start()")
    assert str(mock_mirobo.mock_calls[-1]) == 'call.Vacuum().status()'

    yield from hass.services.async_call(
        DOMAIN, SERVICE_MOVE_REMOTE_CONTROL,
        {"duration": 1000, "rotation": -40, "velocity": -0.1}, blocking=True)
    assert 'call.Vacuum().manual_control(' in str(mock_mirobo.mock_calls[-2])
    assert 'duration=1000' in str(mock_mirobo.mock_calls[-2])
    assert 'rotation=-40' in str(mock_mirobo.mock_calls[-2])
    assert 'velocity=-0.1' in str(mock_mirobo.mock_calls[-2])
    assert str(mock_mirobo.mock_calls[-1]) == 'call.Vacuum().status()'

    yield from hass.services.async_call(
        DOMAIN, SERVICE_STOP_REMOTE_CONTROL, {}, blocking=True)
    assert (str(mock_mirobo.mock_calls[-2])
            == "call.Vacuum().manual_stop()")
    assert str(mock_mirobo.mock_calls[-1]) == 'call.Vacuum().status()'

    yield from hass.services.async_call(
        DOMAIN, SERVICE_MOVE_REMOTE_CONTROL_STEP,
        {"duration": 2000, "rotation": 120, "velocity": 0.1}, blocking=True)
    assert ('call.Vacuum().manual_control_once('
            in str(mock_mirobo.mock_calls[-2]))
    assert 'duration=2000' in str(mock_mirobo.mock_calls[-2])
    assert 'rotation=120' in str(mock_mirobo.mock_calls[-2])
    assert 'velocity=0.1' in str(mock_mirobo.mock_calls[-2])

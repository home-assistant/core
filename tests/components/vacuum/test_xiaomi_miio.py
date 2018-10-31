"""The tests for the Xiaomi vacuum platform."""
import asyncio
from datetime import timedelta, time
from unittest import mock

import pytest

from homeassistant.components.vacuum import (
    ATTR_BATTERY_ICON,
    ATTR_FAN_SPEED, ATTR_FAN_SPEED_LIST, DOMAIN,
    SERVICE_CLEAN_SPOT, SERVICE_LOCATE, SERVICE_RETURN_TO_BASE,
    SERVICE_SEND_COMMAND, SERVICE_SET_FAN_SPEED, SERVICE_START_PAUSE,
    SERVICE_STOP, SERVICE_TOGGLE, SERVICE_TURN_OFF, SERVICE_TURN_ON)
from homeassistant.components.vacuum.xiaomi_miio import (
    ATTR_CLEANED_AREA, ATTR_CLEANING_TIME, ATTR_DO_NOT_DISTURB,
    ATTR_DO_NOT_DISTURB_START, ATTR_DO_NOT_DISTURB_END, ATTR_ERROR,
    ATTR_MAIN_BRUSH_LEFT, ATTR_SIDE_BRUSH_LEFT, ATTR_FILTER_LEFT,
    ATTR_CLEANING_COUNT, ATTR_CLEANED_TOTAL_AREA, ATTR_CLEANING_TOTAL_TIME,
    CONF_HOST, CONF_NAME, CONF_TOKEN,
    SERVICE_MOVE_REMOTE_CONTROL, SERVICE_MOVE_REMOTE_CONTROL_STEP,
    SERVICE_START_REMOTE_CONTROL, SERVICE_STOP_REMOTE_CONTROL)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES, CONF_PLATFORM, STATE_OFF,
    STATE_ON)
from homeassistant.setup import async_setup_component

PLATFORM = 'xiaomi_miio'

# calls made when device status is requested
status_calls = [mock.call.Vacuum().status(),
                mock.call.Vacuum().consumable_status(),
                mock.call.Vacuum().clean_history(),
                mock.call.Vacuum().dnd_status()]


@pytest.fixture
def mock_mirobo_is_off():
    """Mock mock_mirobo."""
    mock_vacuum = mock.MagicMock()
    mock_vacuum.Vacuum().status().data = {'test': 'raw'}
    mock_vacuum.Vacuum().status().is_on = False
    mock_vacuum.Vacuum().status().fanspeed = 38
    mock_vacuum.Vacuum().status().got_error = True
    mock_vacuum.Vacuum().status().error = 'Error message'
    mock_vacuum.Vacuum().status().battery = 82
    mock_vacuum.Vacuum().status().clean_area = 123.43218
    mock_vacuum.Vacuum().status().clean_time = timedelta(
        hours=2, minutes=35, seconds=34)
    mock_vacuum.Vacuum().consumable_status().main_brush_left = timedelta(
        hours=12, minutes=35, seconds=34)
    mock_vacuum.Vacuum().consumable_status().side_brush_left = timedelta(
        hours=12, minutes=35, seconds=34)
    mock_vacuum.Vacuum().consumable_status().filter_left = timedelta(
        hours=12, minutes=35, seconds=34)
    mock_vacuum.Vacuum().clean_history().count = '35'
    mock_vacuum.Vacuum().clean_history().total_area = 123.43218
    mock_vacuum.Vacuum().clean_history().total_duration = timedelta(
        hours=11, minutes=35, seconds=34)
    mock_vacuum.Vacuum().status().state = 'Test Xiaomi Charging'
    mock_vacuum.Vacuum().dnd_status().enabled = True
    mock_vacuum.Vacuum().dnd_status().start = time(hour=22, minute=0)
    mock_vacuum.Vacuum().dnd_status().end = time(hour=6, minute=0)

    with mock.patch.dict('sys.modules', {
        'miio': mock_vacuum,
    }):
        yield mock_vacuum


@pytest.fixture
def mock_mirobo_is_on():
    """Mock mock_mirobo."""
    mock_vacuum = mock.MagicMock()
    mock_vacuum.Vacuum().status().data = {'test': 'raw'}
    mock_vacuum.Vacuum().status().is_on = True
    mock_vacuum.Vacuum().status().fanspeed = 99
    mock_vacuum.Vacuum().status().got_error = False
    mock_vacuum.Vacuum().status().battery = 32
    mock_vacuum.Vacuum().status().clean_area = 133.43218
    mock_vacuum.Vacuum().status().clean_time = timedelta(
        hours=2, minutes=55, seconds=34)
    mock_vacuum.Vacuum().consumable_status().main_brush_left = timedelta(
        hours=11, minutes=35, seconds=34)
    mock_vacuum.Vacuum().consumable_status().side_brush_left = timedelta(
        hours=11, minutes=35, seconds=34)
    mock_vacuum.Vacuum().consumable_status().filter_left = timedelta(
        hours=11, minutes=35, seconds=34)
    mock_vacuum.Vacuum().clean_history().count = '41'
    mock_vacuum.Vacuum().clean_history().total_area = 323.43218
    mock_vacuum.Vacuum().clean_history().total_duration = timedelta(
        hours=11, minutes=15, seconds=34)
    mock_vacuum.Vacuum().status().state = 'Test Xiaomi Cleaning'
    mock_vacuum.Vacuum().dnd_status().enabled = False

    with mock.patch.dict('sys.modules', {
        'miio': mock_vacuum,
    }):
        yield mock_vacuum


@pytest.fixture
def mock_mirobo_errors():
    """Mock mock_mirobo_errors to simulate a bad vacuum status request."""
    mock_vacuum = mock.MagicMock()
    mock_vacuum.Vacuum().status.side_effect = OSError()
    with mock.patch.dict('sys.modules', {
        'miio': mock_vacuum,
    }):
        yield mock_vacuum


@asyncio.coroutine
def test_xiaomi_exceptions(hass, caplog, mock_mirobo_errors):
    """Test vacuum supported features."""
    entity_name = 'test_vacuum_cleaner_error'
    yield from async_setup_component(
        hass, DOMAIN,
        {DOMAIN: {CONF_PLATFORM: PLATFORM,
                  CONF_HOST: '127.0.0.1',
                  CONF_NAME: entity_name,
                  CONF_TOKEN: '12345678901234567890123456789012'}})

    assert 'Initializing with host 127.0.0.1 (token 12345...)' in caplog.text
    assert str(mock_mirobo_errors.mock_calls[-1]) == 'call.Vacuum().status()'
    assert 'ERROR' in caplog.text
    assert 'Got OSError while fetching the state' in caplog.text


@asyncio.coroutine
@pytest.mark.skip(reason="Fails")
def test_xiaomi_vacuum_services(hass, caplog, mock_mirobo_is_off):
    """Test vacuum supported features."""
    entity_name = 'test_vacuum_cleaner_1'
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
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 2047
    assert state.attributes.get(ATTR_DO_NOT_DISTURB) == STATE_ON
    assert state.attributes.get(ATTR_DO_NOT_DISTURB_START) == '22:00:00'
    assert state.attributes.get(ATTR_DO_NOT_DISTURB_END) == '06:00:00'
    assert state.attributes.get(ATTR_ERROR) == 'Error message'
    assert (state.attributes.get(ATTR_BATTERY_ICON)
            == 'mdi:battery-charging-80')
    assert state.attributes.get(ATTR_CLEANING_TIME) == 155
    assert state.attributes.get(ATTR_CLEANED_AREA) == 123
    assert state.attributes.get(ATTR_FAN_SPEED) == 'Quiet'
    assert (state.attributes.get(ATTR_FAN_SPEED_LIST)
            == ['Quiet', 'Balanced', 'Turbo', 'Max'])
    assert state.attributes.get(ATTR_MAIN_BRUSH_LEFT) == 12
    assert state.attributes.get(ATTR_SIDE_BRUSH_LEFT) == 12
    assert state.attributes.get(ATTR_FILTER_LEFT) == 12
    assert state.attributes.get(ATTR_CLEANING_COUNT) == 35
    assert state.attributes.get(ATTR_CLEANED_TOTAL_AREA) == 123
    assert state.attributes.get(ATTR_CLEANING_TOTAL_TIME) == 695

    # Call services
    yield from hass.services.async_call(
        DOMAIN, SERVICE_TURN_ON, blocking=True)

    mock_mirobo_is_off.assert_has_calls(
        [mock.call.Vacuum.start()], any_order=True)
    mock_mirobo_is_off.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_off.reset_mock()

    yield from hass.services.async_call(
        DOMAIN, SERVICE_TURN_OFF, blocking=True)
    mock_mirobo_is_off.assert_has_calls(
        [mock.call.Vacuum().home()], any_order=True)
    mock_mirobo_is_off.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_off.reset_mock()

    yield from hass.services.async_call(
        DOMAIN, SERVICE_TOGGLE, blocking=True)
    mock_mirobo_is_off.assert_has_calls(
        [mock.call.Vacuum().start()], any_order=True)
    mock_mirobo_is_off.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_off.reset_mock()

    yield from hass.services.async_call(
        DOMAIN, SERVICE_STOP, blocking=True)
    mock_mirobo_is_off.assert_has_calls(
        [mock.call.Vacuum().stop()], any_order=True)
    mock_mirobo_is_off.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_off.reset_mock()

    yield from hass.services.async_call(
        DOMAIN, SERVICE_START_PAUSE, blocking=True)
    mock_mirobo_is_off.assert_has_calls(
        [mock.call.Vacuum().pause()], any_order=True)
    mock_mirobo_is_off.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_off.reset_mock()

    yield from hass.services.async_call(
        DOMAIN, SERVICE_RETURN_TO_BASE, blocking=True)
    mock_mirobo_is_off.assert_has_calls(
        [mock.call.Vacuum().home()], any_order=True)
    mock_mirobo_is_off.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_off.reset_mock()

    yield from hass.services.async_call(
        DOMAIN, SERVICE_LOCATE, blocking=True)
    mock_mirobo_is_off.assert_has_calls(
        [mock.call.Vacuum().find()], any_order=True)
    mock_mirobo_is_off.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_off.reset_mock()

    yield from hass.services.async_call(
        DOMAIN, SERVICE_CLEAN_SPOT, {}, blocking=True)
    mock_mirobo_is_off.assert_has_calls(
        [mock.call.Vacuum().spot()], any_order=True)
    mock_mirobo_is_off.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_off.reset_mock()

    # Set speed service:
    yield from hass.services.async_call(
        DOMAIN, SERVICE_SET_FAN_SPEED, {"fan_speed": 60}, blocking=True)
    mock_mirobo_is_off.assert_has_calls(
        [mock.call.Vacuum().set_fan_speed(60)], any_order=True)
    mock_mirobo_is_off.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_off.reset_mock()

    yield from hass.services.async_call(
        DOMAIN, SERVICE_SET_FAN_SPEED, {"fan_speed": "turbo"}, blocking=True)
    mock_mirobo_is_off.assert_has_calls(
        [mock.call.Vacuum().set_fan_speed(77)], any_order=True)
    mock_mirobo_is_off.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_off.reset_mock()

    assert 'ERROR' not in caplog.text
    yield from hass.services.async_call(
        DOMAIN, SERVICE_SET_FAN_SPEED, {"fan_speed": "invent"}, blocking=True)
    assert 'ERROR' in caplog.text

    yield from hass.services.async_call(
        DOMAIN, SERVICE_SEND_COMMAND,
        {"command": "raw"}, blocking=True)
    mock_mirobo_is_off.assert_has_calls(
        [mock.call.Vacuum().raw_command('raw', None)], any_order=True)
    mock_mirobo_is_off.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_off.reset_mock()

    yield from hass.services.async_call(
        DOMAIN, SERVICE_SEND_COMMAND,
        {"command": "raw", "params": {"k1": 2}}, blocking=True)
    mock_mirobo_is_off.assert_has_calls(
        [mock.call.Vacuum().raw_command('raw', {'k1': 2})], any_order=True)
    mock_mirobo_is_off.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_off.reset_mock()


@asyncio.coroutine
@pytest.mark.skip(reason="Fails")
def test_xiaomi_specific_services(hass, caplog, mock_mirobo_is_on):
    """Test vacuum supported features."""
    entity_name = 'test_vacuum_cleaner_2'
    entity_id = '{}.{}'.format(DOMAIN, entity_name)

    yield from async_setup_component(
        hass, DOMAIN,
        {DOMAIN: {CONF_PLATFORM: PLATFORM,
                  CONF_HOST: '192.168.1.100',
                  CONF_NAME: entity_name,
                  CONF_TOKEN: '12345678901234567890123456789012'}})

    assert 'Initializing with host 192.168.1.100 (token 12345' in caplog.text

    # Check state attributes
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 2047
    assert state.attributes.get(ATTR_DO_NOT_DISTURB) == STATE_OFF
    assert state.attributes.get(ATTR_ERROR) is None
    assert (state.attributes.get(ATTR_BATTERY_ICON)
            == 'mdi:battery-30')
    assert state.attributes.get(ATTR_CLEANING_TIME) == 175
    assert state.attributes.get(ATTR_CLEANED_AREA) == 133
    assert state.attributes.get(ATTR_FAN_SPEED) == 99
    assert (state.attributes.get(ATTR_FAN_SPEED_LIST)
            == ['Quiet', 'Balanced', 'Turbo', 'Max'])
    assert state.attributes.get(ATTR_MAIN_BRUSH_LEFT) == 11
    assert state.attributes.get(ATTR_SIDE_BRUSH_LEFT) == 11
    assert state.attributes.get(ATTR_FILTER_LEFT) == 11
    assert state.attributes.get(ATTR_CLEANING_COUNT) == 41
    assert state.attributes.get(ATTR_CLEANED_TOTAL_AREA) == 323
    assert state.attributes.get(ATTR_CLEANING_TOTAL_TIME) == 675

    # Xiaomi vacuum specific services:
    yield from hass.services.async_call(
        DOMAIN, SERVICE_START_REMOTE_CONTROL,
        {ATTR_ENTITY_ID: entity_id}, blocking=True)

    mock_mirobo_is_on.assert_has_calls(
        [mock.call.Vacuum().manual_start()], any_order=True)
    mock_mirobo_is_on.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_on.reset_mock()

    control = {"duration": 1000, "rotation": -40, "velocity": -0.1}
    yield from hass.services.async_call(
        DOMAIN, SERVICE_MOVE_REMOTE_CONTROL,
        control, blocking=True)
    mock_mirobo_is_on.assert_has_calls(
        [mock.call.Vacuum().manual_control(control)], any_order=True)
    mock_mirobo_is_on.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_on.reset_mock()

    yield from hass.services.async_call(
        DOMAIN, SERVICE_STOP_REMOTE_CONTROL, {}, blocking=True)
    mock_mirobo_is_on.assert_has_calls(
        [mock.call.Vacuum().manual_stop()], any_order=True)
    mock_mirobo_is_on.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_on.reset_mock()

    control_once = {"duration": 2000, "rotation": 120, "velocity": 0.1}
    yield from hass.services.async_call(
        DOMAIN, SERVICE_MOVE_REMOTE_CONTROL_STEP,
        control_once, blocking=True)
    mock_mirobo_is_on.assert_has_calls(
        [mock.call.Vacuum().manual_control_once(control_once)], any_order=True)
    mock_mirobo_is_on.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_on.reset_mock()

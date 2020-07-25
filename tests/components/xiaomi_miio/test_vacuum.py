"""The tests for the Xiaomi vacuum platform."""
from datetime import datetime, time, timedelta
from unittest import mock

import pytest
from pytz import utc

from homeassistant.components.vacuum import (
    ATTR_BATTERY_ICON,
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
    DOMAIN,
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    STATE_CLEANING,
    STATE_ERROR,
)
from homeassistant.components.xiaomi_miio.const import DOMAIN as XIAOMI_DOMAIN
from homeassistant.components.xiaomi_miio.vacuum import (
    ATTR_CLEANED_AREA,
    ATTR_CLEANED_TOTAL_AREA,
    ATTR_CLEANING_COUNT,
    ATTR_CLEANING_TIME,
    ATTR_CLEANING_TOTAL_TIME,
    ATTR_DO_NOT_DISTURB,
    ATTR_DO_NOT_DISTURB_END,
    ATTR_DO_NOT_DISTURB_START,
    ATTR_ERROR,
    ATTR_FILTER_LEFT,
    ATTR_MAIN_BRUSH_LEFT,
    ATTR_SIDE_BRUSH_LEFT,
    ATTR_TIMERS,
    CONF_HOST,
    CONF_NAME,
    CONF_TOKEN,
    SERVICE_CLEAN_SEGMENT,
    SERVICE_CLEAN_ZONE,
    SERVICE_GOTO,
    SERVICE_MOVE_REMOTE_CONTROL,
    SERVICE_MOVE_REMOTE_CONTROL_STEP,
    SERVICE_START_REMOTE_CONTROL,
    SERVICE_STOP_REMOTE_CONTROL,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    CONF_PLATFORM,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.setup import async_setup_component

PLATFORM = "xiaomi_miio"

# calls made when device status is requested
STATUS_CALLS = [
    mock.call.status(),
    mock.call.consumable_status(),
    mock.call.clean_history(),
    mock.call.dnd_status(),
    mock.call.timer(),
]


@pytest.fixture(name="mock_mirobo_is_got_error")
def mirobo_is_got_error_fixture():
    """Mock mock_mirobo."""
    mock_vacuum = mock.MagicMock()
    mock_vacuum.status().data = {"test": "raw"}
    mock_vacuum.status().is_on = False
    mock_vacuum.status().fanspeed = 38
    mock_vacuum.status().got_error = True
    mock_vacuum.status().error = "Error message"
    mock_vacuum.status().battery = 82
    mock_vacuum.status().clean_area = 123.43218
    mock_vacuum.status().clean_time = timedelta(hours=2, minutes=35, seconds=34)
    mock_vacuum.consumable_status().main_brush_left = timedelta(
        hours=12, minutes=35, seconds=34
    )
    mock_vacuum.consumable_status().side_brush_left = timedelta(
        hours=12, minutes=35, seconds=34
    )
    mock_vacuum.consumable_status().filter_left = timedelta(
        hours=12, minutes=35, seconds=34
    )
    mock_vacuum.clean_history().count = "35"
    mock_vacuum.clean_history().total_area = 123.43218
    mock_vacuum.clean_history().total_duration = timedelta(
        hours=11, minutes=35, seconds=34
    )
    mock_vacuum.status().state = "Test Xiaomi Charging"
    mock_vacuum.dnd_status().enabled = True
    mock_vacuum.dnd_status().start = time(hour=22, minute=0)
    mock_vacuum.dnd_status().end = time(hour=6, minute=0)

    mock_timer_1 = mock.MagicMock()
    mock_timer_1.enabled = True
    mock_timer_1.cron = "5 5 1 8 1"
    mock_timer_1.next_schedule = datetime(2020, 5, 23, 13, 21, 10, tzinfo=utc)

    mock_timer_2 = mock.MagicMock()
    mock_timer_2.enabled = False
    mock_timer_2.cron = "5 5 1 8 2"
    mock_timer_2.next_schedule = datetime(2020, 5, 23, 13, 21, 10, tzinfo=utc)

    mock_vacuum.timer.return_value = [mock_timer_1, mock_timer_2]

    with mock.patch(
        "homeassistant.components.xiaomi_miio.vacuum.Vacuum"
    ) as mock_vaccum_cls:
        mock_vaccum_cls.return_value = mock_vacuum
        yield mock_vacuum


old_fanspeeds = {
    "Silent": 38,
    "Standard": 60,
    "Medium": 77,
    "Turbo": 90,
}
new_fanspeeds = {
    "Silent": 101,
    "Standard": 102,
    "Medium": 103,
    "Turbo": 104,
    "Gentle": 105,
}


@pytest.fixture(name="mock_mirobo_fanspeeds", params=[old_fanspeeds, new_fanspeeds])
def mirobo_old_speeds_fixture(request):
    """Fixture for testing both types of fanspeeds."""
    mock_vacuum = mock.MagicMock()
    mock_vacuum.status().battery = 32
    mock_vacuum.fan_speed_presets.return_value = request.param
    mock_vacuum.status().fanspeed = list(request.param.values())[0]

    with mock.patch(
        "homeassistant.components.xiaomi_miio.vacuum.Vacuum"
    ) as mock_vaccum_cls:
        mock_vaccum_cls.return_value = mock_vacuum
        yield mock_vacuum


@pytest.fixture(name="mock_mirobo_is_on")
def mirobo_is_on_fixture():
    """Mock mock_mirobo."""
    mock_vacuum = mock.MagicMock()
    mock_vacuum.status().data = {"test": "raw"}
    mock_vacuum.status().is_on = True
    mock_vacuum.status().fanspeed = 99
    mock_vacuum.status().got_error = False
    mock_vacuum.status().battery = 32
    mock_vacuum.status().clean_area = 133.43218
    mock_vacuum.status().clean_time = timedelta(hours=2, minutes=55, seconds=34)
    mock_vacuum.consumable_status().main_brush_left = timedelta(
        hours=11, minutes=35, seconds=34
    )
    mock_vacuum.consumable_status().side_brush_left = timedelta(
        hours=11, minutes=35, seconds=34
    )
    mock_vacuum.consumable_status().filter_left = timedelta(
        hours=11, minutes=35, seconds=34
    )
    mock_vacuum.clean_history().count = "41"
    mock_vacuum.clean_history().total_area = 323.43218
    mock_vacuum.clean_history().total_duration = timedelta(
        hours=11, minutes=15, seconds=34
    )
    mock_vacuum.status().state = "Test Xiaomi Cleaning"
    mock_vacuum.status().state_code = 5
    mock_vacuum.dnd_status().enabled = False

    mock_timer_1 = mock.MagicMock()
    mock_timer_1.enabled = True
    mock_timer_1.cron = "5 5 1 8 1"
    mock_timer_1.next_schedule = datetime(2020, 5, 23, 13, 21, 10, tzinfo=utc)

    mock_timer_2 = mock.MagicMock()
    mock_timer_2.enabled = False
    mock_timer_2.cron = "5 5 1 8 2"
    mock_timer_2.next_schedule = datetime(2020, 5, 23, 13, 21, 10, tzinfo=utc)

    mock_vacuum.timer.return_value = [mock_timer_1, mock_timer_2]

    with mock.patch(
        "homeassistant.components.xiaomi_miio.vacuum.Vacuum"
    ) as mock_vaccum_cls:
        mock_vaccum_cls.return_value = mock_vacuum
        yield mock_vacuum


@pytest.fixture(name="mock_mirobo_errors")
def mirobo_errors_fixture():
    """Mock mock_mirobo_errors to simulate a bad vacuum status request."""
    mock_vacuum = mock.MagicMock()
    mock_vacuum.status.side_effect = OSError()
    with mock.patch(
        "homeassistant.components.xiaomi_miio.vacuum.Vacuum"
    ) as mock_vaccum_cls:
        mock_vaccum_cls.return_value = mock_vacuum
        yield mock_vacuum


async def test_xiaomi_exceptions(hass, caplog, mock_mirobo_errors):
    """Test vacuum supported features."""
    entity_name = "test_vacuum_cleaner_error"
    await setup_component(hass, entity_name)

    assert "Initializing with host 192.168.1.100 (token 12345...)" in caplog.text
    assert mock_mirobo_errors.status.call_count == 1
    assert "ERROR" in caplog.text
    assert "Got OSError while fetching the state" in caplog.text


async def test_xiaomi_vacuum_services(hass, caplog, mock_mirobo_is_got_error):
    """Test vacuum supported features."""
    entity_name = "test_vacuum_cleaner_1"
    entity_id = await setup_component(hass, entity_name)

    assert "Initializing with host 192.168.1.100 (token 12345...)" in caplog.text

    # Check state attributes
    state = hass.states.get(entity_id)

    assert state.state == STATE_ERROR
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 14204
    assert state.attributes.get(ATTR_DO_NOT_DISTURB) == STATE_ON
    assert state.attributes.get(ATTR_DO_NOT_DISTURB_START) == "22:00:00"
    assert state.attributes.get(ATTR_DO_NOT_DISTURB_END) == "06:00:00"
    assert state.attributes.get(ATTR_ERROR) == "Error message"
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-80"
    assert state.attributes.get(ATTR_CLEANING_TIME) == 155
    assert state.attributes.get(ATTR_CLEANED_AREA) == 123
    assert state.attributes.get(ATTR_MAIN_BRUSH_LEFT) == 12
    assert state.attributes.get(ATTR_SIDE_BRUSH_LEFT) == 12
    assert state.attributes.get(ATTR_FILTER_LEFT) == 12
    assert state.attributes.get(ATTR_CLEANING_COUNT) == 35
    assert state.attributes.get(ATTR_CLEANED_TOTAL_AREA) == 123
    assert state.attributes.get(ATTR_CLEANING_TOTAL_TIME) == 695
    assert state.attributes.get(ATTR_TIMERS) == [
        {
            "enabled": True,
            "cron": "5 5 1 8 1",
            "next_schedule": datetime(2020, 5, 23, 13, 21, 10, tzinfo=utc),
        },
        {
            "enabled": False,
            "cron": "5 5 1 8 2",
            "next_schedule": datetime(2020, 5, 23, 13, 21, 10, tzinfo=utc),
        },
    ]

    # Call services
    await hass.services.async_call(
        DOMAIN, SERVICE_START, {"entity_id": entity_id}, blocking=True
    )
    mock_mirobo_is_got_error.assert_has_calls(
        [mock.call.resume_or_start()], any_order=True
    )
    mock_mirobo_is_got_error.assert_has_calls(STATUS_CALLS, any_order=True)
    mock_mirobo_is_got_error.reset_mock()

    await hass.services.async_call(
        DOMAIN, SERVICE_STOP, {"entity_id": entity_id}, blocking=True
    )
    mock_mirobo_is_got_error.assert_has_calls([mock.call.stop()], any_order=True)
    mock_mirobo_is_got_error.assert_has_calls(STATUS_CALLS, any_order=True)
    mock_mirobo_is_got_error.reset_mock()

    await hass.services.async_call(
        DOMAIN, SERVICE_RETURN_TO_BASE, {"entity_id": entity_id}, blocking=True
    )
    mock_mirobo_is_got_error.assert_has_calls([mock.call.home()], any_order=True)
    mock_mirobo_is_got_error.assert_has_calls(STATUS_CALLS, any_order=True)
    mock_mirobo_is_got_error.reset_mock()

    await hass.services.async_call(
        DOMAIN, SERVICE_LOCATE, {"entity_id": entity_id}, blocking=True
    )
    mock_mirobo_is_got_error.assert_has_calls([mock.call.find()], any_order=True)
    mock_mirobo_is_got_error.assert_has_calls(STATUS_CALLS, any_order=True)
    mock_mirobo_is_got_error.reset_mock()

    await hass.services.async_call(
        DOMAIN, SERVICE_CLEAN_SPOT, {"entity_id": entity_id}, blocking=True
    )
    mock_mirobo_is_got_error.assert_has_calls([mock.call.spot()], any_order=True)
    mock_mirobo_is_got_error.assert_has_calls(STATUS_CALLS, any_order=True)
    mock_mirobo_is_got_error.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        {"entity_id": entity_id, "command": "raw"},
        blocking=True,
    )
    mock_mirobo_is_got_error.assert_has_calls(
        [mock.call.raw_command("raw", None)], any_order=True
    )
    mock_mirobo_is_got_error.assert_has_calls(STATUS_CALLS, any_order=True)
    mock_mirobo_is_got_error.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        {"entity_id": entity_id, "command": "raw", "params": {"k1": 2}},
        blocking=True,
    )
    mock_mirobo_is_got_error.assert_has_calls(
        [mock.call.raw_command("raw", {"k1": 2})], any_order=True
    )
    mock_mirobo_is_got_error.assert_has_calls(STATUS_CALLS, any_order=True)
    mock_mirobo_is_got_error.reset_mock()


async def test_xiaomi_specific_services(hass, caplog, mock_mirobo_is_on):
    """Test vacuum supported features."""
    entity_name = "test_vacuum_cleaner_2"
    entity_id = await setup_component(hass, entity_name)

    assert "Initializing with host 192.168.1.100 (token 12345" in caplog.text

    # Check state attributes
    state = hass.states.get(entity_id)
    assert state.state == STATE_CLEANING
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 14204
    assert state.attributes.get(ATTR_DO_NOT_DISTURB) == STATE_OFF
    assert state.attributes.get(ATTR_ERROR) is None
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-30"
    assert state.attributes.get(ATTR_CLEANING_TIME) == 175
    assert state.attributes.get(ATTR_CLEANED_AREA) == 133
    assert state.attributes.get(ATTR_MAIN_BRUSH_LEFT) == 11
    assert state.attributes.get(ATTR_SIDE_BRUSH_LEFT) == 11
    assert state.attributes.get(ATTR_FILTER_LEFT) == 11
    assert state.attributes.get(ATTR_CLEANING_COUNT) == 41
    assert state.attributes.get(ATTR_CLEANED_TOTAL_AREA) == 323
    assert state.attributes.get(ATTR_CLEANING_TOTAL_TIME) == 675
    assert state.attributes.get(ATTR_TIMERS) == [
        {
            "enabled": True,
            "cron": "5 5 1 8 1",
            "next_schedule": datetime(2020, 5, 23, 13, 21, 10, tzinfo=utc),
        },
        {
            "enabled": False,
            "cron": "5 5 1 8 2",
            "next_schedule": datetime(2020, 5, 23, 13, 21, 10, tzinfo=utc),
        },
    ]

    # Xiaomi vacuum specific services:
    await hass.services.async_call(
        XIAOMI_DOMAIN,
        SERVICE_START_REMOTE_CONTROL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_mirobo_is_on.assert_has_calls([mock.call.manual_start()], any_order=True)
    mock_mirobo_is_on.assert_has_calls(STATUS_CALLS, any_order=True)
    mock_mirobo_is_on.reset_mock()

    control = {"duration": 1000, "rotation": -40, "velocity": -0.1}
    await hass.services.async_call(
        XIAOMI_DOMAIN,
        SERVICE_MOVE_REMOTE_CONTROL,
        {**control, ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_mirobo_is_on.manual_control.assert_has_calls(
        [mock.call(**control)], any_order=True
    )
    mock_mirobo_is_on.assert_has_calls(STATUS_CALLS, any_order=True)
    mock_mirobo_is_on.reset_mock()

    await hass.services.async_call(
        XIAOMI_DOMAIN,
        SERVICE_STOP_REMOTE_CONTROL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_mirobo_is_on.assert_has_calls([mock.call.manual_stop()], any_order=True)
    mock_mirobo_is_on.assert_has_calls(STATUS_CALLS, any_order=True)
    mock_mirobo_is_on.reset_mock()

    control_once = {"duration": 2000, "rotation": 120, "velocity": 0.1}
    await hass.services.async_call(
        XIAOMI_DOMAIN,
        SERVICE_MOVE_REMOTE_CONTROL_STEP,
        {**control_once, ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_mirobo_is_on.manual_control_once.assert_has_calls(
        [mock.call(**control_once)], any_order=True
    )
    mock_mirobo_is_on.assert_has_calls(STATUS_CALLS, any_order=True)
    mock_mirobo_is_on.reset_mock()

    control = {"zone": [[123, 123, 123, 123]], "repeats": 2}
    await hass.services.async_call(
        XIAOMI_DOMAIN,
        SERVICE_CLEAN_ZONE,
        {**control, ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock_mirobo_is_on.zoned_clean.assert_has_calls(
        [mock.call([[123, 123, 123, 123, 2]])], any_order=True
    )
    mock_mirobo_is_on.assert_has_calls(STATUS_CALLS, any_order=True)
    mock_mirobo_is_on.reset_mock()


async def test_xiaomi_vacuum_fanspeeds(hass, caplog, mock_mirobo_fanspeeds):
    """Test Xiaomi vacuum fanspeeds."""
    entity_name = "test_vacuum_cleaner_2"
    entity_id = await setup_component(hass, entity_name)

    assert "Initializing with host 192.168.1.100 (token 12345" in caplog.text

    state = hass.states.get(entity_id)
    assert state.attributes.get(ATTR_FAN_SPEED) == "Silent"
    fanspeeds = state.attributes.get(ATTR_FAN_SPEED_LIST)
    for speed in ["Silent", "Standard", "Medium", "Turbo"]:
        assert speed in fanspeeds

    # Set speed service:
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_SPEED,
        {"entity_id": entity_id, "fan_speed": 60},
        blocking=True,
    )
    mock_mirobo_fanspeeds.assert_has_calls(
        [mock.call.set_fan_speed(60)], any_order=True
    )
    mock_mirobo_fanspeeds.assert_has_calls(STATUS_CALLS, any_order=True)
    mock_mirobo_fanspeeds.reset_mock()

    fan_speed_dict = mock_mirobo_fanspeeds.fan_speed_presets()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_SPEED,
        {"entity_id": entity_id, "fan_speed": "Medium"},
        blocking=True,
    )
    mock_mirobo_fanspeeds.assert_has_calls(
        [mock.call.set_fan_speed(fan_speed_dict["Medium"])], any_order=True
    )
    mock_mirobo_fanspeeds.assert_has_calls(STATUS_CALLS, any_order=True)
    mock_mirobo_fanspeeds.reset_mock()

    assert "ERROR" not in caplog.text
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_FAN_SPEED,
        {"entity_id": entity_id, "fan_speed": "invent"},
        blocking=True,
    )
    assert "ERROR" in caplog.text


async def test_xiaomi_vacuum_goto_service(hass, caplog, mock_mirobo_is_on):
    """Test vacuum supported features."""
    entity_name = "test_vacuum_cleaner_2"
    entity_id = await setup_component(hass, entity_name)

    data = {"entity_id": entity_id, "x_coord": 25500, "y_coord": 25500}
    await hass.services.async_call(XIAOMI_DOMAIN, SERVICE_GOTO, data, blocking=True)
    mock_mirobo_is_on.goto.assert_has_calls(
        [mock.call(x_coord=data["x_coord"], y_coord=data["y_coord"])], any_order=True
    )
    mock_mirobo_is_on.assert_has_calls(STATUS_CALLS, any_order=True)


async def test_xiaomi_vacuum_clean_segment_service(hass, caplog, mock_mirobo_is_on):
    """Test vacuum supported features."""
    entity_name = "test_vacuum_cleaner_2"
    entity_id = await setup_component(hass, entity_name)

    data = {"entity_id": entity_id, "segments": ["1", "2"]}
    await hass.services.async_call(
        XIAOMI_DOMAIN, SERVICE_CLEAN_SEGMENT, data, blocking=True
    )
    mock_mirobo_is_on.segment_clean.assert_has_calls(
        [mock.call(segments=[int(i) for i in data["segments"]])], any_order=True
    )
    mock_mirobo_is_on.assert_has_calls(STATUS_CALLS, any_order=True)


async def test_xiaomi_vacuum_clean_segment_service_single_segment(
    hass, caplog, mock_mirobo_is_on
):
    """Test vacuum supported features."""
    entity_name = "test_vacuum_cleaner_2"
    entity_id = await setup_component(hass, entity_name)

    data = {"entity_id": entity_id, "segments": 1}
    await hass.services.async_call(
        XIAOMI_DOMAIN, SERVICE_CLEAN_SEGMENT, data, blocking=True
    )
    mock_mirobo_is_on.segment_clean.assert_has_calls(
        [mock.call(segments=[data["segments"]])], any_order=True
    )
    mock_mirobo_is_on.assert_has_calls(STATUS_CALLS, any_order=True)


async def setup_component(hass, entity_name):
    """Set up vacuum component."""
    entity_id = f"{DOMAIN}.{entity_name}"

    await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                CONF_PLATFORM: PLATFORM,
                CONF_HOST: "192.168.1.100",
                CONF_NAME: entity_name,
                CONF_TOKEN: "12345678901234567890123456789012",
            }
        },
    )
    await hass.async_block_till_done()
    return entity_id

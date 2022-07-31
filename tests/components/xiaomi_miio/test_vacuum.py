"""The tests for the Xiaomi vacuum platform."""
from datetime import datetime, time, timedelta
from unittest import mock
from unittest.mock import MagicMock, patch

from miio import DeviceException
import pytest

from homeassistant.components.vacuum import (
    ATTR_BATTERY_ICON,
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
    DOMAIN,
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    STATE_CLEANING,
    STATE_ERROR,
)
from homeassistant.components.xiaomi_miio.const import (
    CONF_DEVICE,
    CONF_FLOW_TYPE,
    CONF_MAC,
    DOMAIN as XIAOMI_DOMAIN,
    MODELS_VACUUM,
)
from homeassistant.components.xiaomi_miio.vacuum import (
    ATTR_ERROR,
    ATTR_TIMERS,
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
    CONF_HOST,
    CONF_MODEL,
    CONF_TOKEN,
    STATE_UNAVAILABLE,
)
from homeassistant.util import dt as dt_util

from . import TEST_MAC

from tests.common import MockConfigEntry, async_fire_time_changed

# pylint: disable=consider-using-tuple

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
    mock_vacuum = MagicMock()
    mock_vacuum.status().data = {"test": "raw"}
    mock_vacuum.status().is_on = False
    mock_vacuum.status().fanspeed = 38
    mock_vacuum.status().got_error = True
    mock_vacuum.status().error = "Error message"
    mock_vacuum.status().battery = 82
    mock_vacuum.status().clean_area = 123.43218
    mock_vacuum.status().clean_time = timedelta(hours=2, minutes=35, seconds=34)
    mock_vacuum.last_clean_details().start = datetime(
        2020, 4, 1, 13, 21, 10, tzinfo=dt_util.UTC
    )
    mock_vacuum.last_clean_details().end = datetime(
        2020, 4, 1, 13, 21, 10, tzinfo=dt_util.UTC
    )
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

    mock_timer_1 = MagicMock()
    mock_timer_1.enabled = True
    mock_timer_1.cron = "5 5 1 8 1"
    mock_timer_1.next_schedule = datetime(2020, 5, 23, 13, 21, 10, tzinfo=dt_util.UTC)

    mock_timer_2 = MagicMock()
    mock_timer_2.enabled = False
    mock_timer_2.cron = "5 5 1 8 2"
    mock_timer_2.next_schedule = datetime(2020, 5, 23, 13, 21, 10, tzinfo=dt_util.UTC)

    mock_vacuum.timer.return_value = [mock_timer_1, mock_timer_2]

    with patch(
        "homeassistant.components.xiaomi_miio.RoborockVacuum"
    ) as mock_vacuum_cls:
        mock_vacuum_cls.return_value = mock_vacuum
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
    mock_vacuum = MagicMock()
    mock_vacuum.status().battery = 32
    mock_vacuum.fan_speed_presets.return_value = request.param
    mock_vacuum.status().fanspeed = list(request.param.values())[0]
    mock_vacuum.last_clean_details().start = datetime(
        2020, 4, 1, 13, 21, 10, tzinfo=dt_util.UTC
    )
    mock_vacuum.last_clean_details().end = datetime(
        2020, 4, 1, 13, 21, 10, tzinfo=dt_util.UTC
    )

    with patch(
        "homeassistant.components.xiaomi_miio.RoborockVacuum"
    ) as mock_vacuum_cls:
        mock_vacuum_cls.return_value = mock_vacuum
        yield mock_vacuum


@pytest.fixture(name="mock_mirobo_is_on")
def mirobo_is_on_fixture():
    """Mock mock_mirobo."""
    mock_vacuum = MagicMock()
    mock_vacuum.status().data = {"test": "raw"}
    mock_vacuum.status().is_on = True
    mock_vacuum.fan_speed_presets.return_value = new_fanspeeds
    mock_vacuum.status().fanspeed = list(new_fanspeeds.values())[0]
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
    mock_vacuum.last_clean_details().start = datetime(
        2020, 4, 1, 13, 21, 10, tzinfo=dt_util.UTC
    )
    mock_vacuum.last_clean_details().end = datetime(
        2020, 4, 1, 13, 21, 10, tzinfo=dt_util.UTC
    )
    mock_vacuum.last_clean_details().duration = timedelta(
        hours=11, minutes=15, seconds=34
    )
    mock_vacuum.last_clean_details().area = 133.43218
    mock_vacuum.last_clean_details().error_code = 1
    mock_vacuum.last_clean_details().error = "test_error_code"
    mock_vacuum.last_clean_details().complete = True

    mock_timer_1 = MagicMock()
    mock_timer_1.enabled = True
    mock_timer_1.cron = "5 5 1 8 1"
    mock_timer_1.next_schedule = datetime(2020, 5, 23, 13, 21, 10, tzinfo=dt_util.UTC)

    mock_timer_2 = MagicMock()
    mock_timer_2.enabled = False
    mock_timer_2.cron = "5 5 1 8 2"
    mock_timer_2.next_schedule = datetime(2020, 5, 23, 13, 21, 10, tzinfo=dt_util.UTC)

    mock_vacuum.timer.return_value = [mock_timer_1, mock_timer_2]

    with patch(
        "homeassistant.components.xiaomi_miio.RoborockVacuum"
    ) as mock_vacuum_cls:
        mock_vacuum_cls.return_value = mock_vacuum
        yield mock_vacuum


async def test_xiaomi_exceptions(hass, mock_mirobo_is_on):
    """Test error logging on exceptions."""
    entity_name = "test_vacuum_cleaner_error"
    entity_id = await setup_component(hass, entity_name)

    def is_available():
        state = hass.states.get(entity_id)
        return state.state != STATE_UNAVAILABLE

    # The initial setup has to be done successfully
    assert is_available()

    # Second update causes an exception, which should be logged
    mock_mirobo_is_on.status.side_effect = DeviceException("dummy exception")
    future = dt_util.utcnow() + timedelta(seconds=60)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert not is_available()

    # Third update does not get logged as the device is already unavailable,
    # so we clear the log and reset the status to test that
    mock_mirobo_is_on.status.reset_mock()
    future += timedelta(seconds=60)
    async_fire_time_changed(hass, future)
    await hass.async_block_till_done()

    assert not is_available()
    assert mock_mirobo_is_on.status.call_count == 1


async def test_xiaomi_vacuum_services(hass, mock_mirobo_is_got_error):
    """Test vacuum supported features."""
    entity_name = "test_vacuum_cleaner_1"
    entity_id = await setup_component(hass, entity_name)

    # Check state attributes
    state = hass.states.get(entity_id)

    assert state.state == STATE_ERROR
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 14204
    assert state.attributes.get(ATTR_ERROR) == "Error message"
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-80"
    assert state.attributes.get(ATTR_TIMERS) == [
        {
            "enabled": True,
            "cron": "5 5 1 8 1",
            "next_schedule": datetime(2020, 5, 23, 13, 21, 10, tzinfo=dt_util.UTC),
        },
        {
            "enabled": False,
            "cron": "5 5 1 8 2",
            "next_schedule": datetime(2020, 5, 23, 13, 21, 10, tzinfo=dt_util.UTC),
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
        DOMAIN, SERVICE_PAUSE, {"entity_id": entity_id}, blocking=True
    )
    mock_mirobo_is_got_error.assert_has_calls([mock.call.pause()], any_order=True)
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


@pytest.mark.parametrize(
    "error, status_calls",
    [(None, STATUS_CALLS), (DeviceException("dummy exception"), [])],
)
@pytest.mark.parametrize(
    "service, service_data, device_method, device_method_call",
    [
        (
            SERVICE_START_REMOTE_CONTROL,
            {ATTR_ENTITY_ID: "vacuum.test_vacuum_cleaner_2"},
            "manual_start",
            mock.call(),
        ),
        (
            SERVICE_MOVE_REMOTE_CONTROL,
            {
                ATTR_ENTITY_ID: "vacuum.test_vacuum_cleaner_2",
                "duration": 1000,
                "rotation": -40,
                "velocity": -0.1,
            },
            "manual_control",
            mock.call(
                **{
                    "duration": 1000,
                    "rotation": -40,
                    "velocity": -0.1,
                }
            ),
        ),
        (
            SERVICE_STOP_REMOTE_CONTROL,
            {
                ATTR_ENTITY_ID: "vacuum.test_vacuum_cleaner_2",
            },
            "manual_stop",
            mock.call(),
        ),
        (
            SERVICE_MOVE_REMOTE_CONTROL_STEP,
            {
                ATTR_ENTITY_ID: "vacuum.test_vacuum_cleaner_2",
                "duration": 2000,
                "rotation": 120,
                "velocity": 0.1,
            },
            "manual_control_once",
            mock.call(
                **{
                    "duration": 2000,
                    "rotation": 120,
                    "velocity": 0.1,
                }
            ),
        ),
        (
            SERVICE_CLEAN_ZONE,
            {
                ATTR_ENTITY_ID: "vacuum.test_vacuum_cleaner_2",
                "zone": [[123, 123, 123, 123]],
                "repeats": 2,
            },
            "zoned_clean",
            mock.call([[123, 123, 123, 123, 2]]),
        ),
        (
            SERVICE_GOTO,
            {
                ATTR_ENTITY_ID: "vacuum.test_vacuum_cleaner_2",
                "x_coord": 25500,
                "y_coord": 26500,
            },
            "goto",
            mock.call(x_coord=25500, y_coord=26500),
        ),
        (
            SERVICE_CLEAN_SEGMENT,
            {
                ATTR_ENTITY_ID: "vacuum.test_vacuum_cleaner_2",
                "segments": ["1", "2"],
            },
            "segment_clean",
            mock.call(segments=[int(i) for i in ["1", "2"]]),
        ),
        (
            SERVICE_CLEAN_SEGMENT,
            {
                ATTR_ENTITY_ID: "vacuum.test_vacuum_cleaner_2",
                "segments": 1,
            },
            "segment_clean",
            mock.call(segments=[1]),
        ),
    ],
)
async def test_xiaomi_specific_services(
    hass,
    mock_mirobo_is_on,
    service,
    service_data,
    device_method,
    device_method_call,
    error,
    status_calls,
):
    """Test vacuum supported features."""
    entity_name = "test_vacuum_cleaner_2"
    entity_id = await setup_component(hass, entity_name)

    # Check state attributes
    state = hass.states.get(entity_id)
    assert state.state == STATE_CLEANING
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 14204
    assert state.attributes.get(ATTR_ERROR) is None
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-30"
    assert state.attributes.get(ATTR_TIMERS) == [
        {
            "enabled": True,
            "cron": "5 5 1 8 1",
            "next_schedule": datetime(2020, 5, 23, 13, 21, 10, tzinfo=dt_util.UTC),
        },
        {
            "enabled": False,
            "cron": "5 5 1 8 2",
            "next_schedule": datetime(2020, 5, 23, 13, 21, 10, tzinfo=dt_util.UTC),
        },
    ]

    # Xiaomi vacuum specific services:
    device_method_attr = getattr(mock_mirobo_is_on, device_method)
    device_method_attr.side_effect = error

    await hass.services.async_call(
        XIAOMI_DOMAIN,
        service,
        service_data,
        blocking=True,
    )

    device_method_attr.assert_has_calls([device_method_call], any_order=True)
    mock_mirobo_is_on.assert_has_calls(status_calls, any_order=True)
    mock_mirobo_is_on.reset_mock()


async def test_xiaomi_vacuum_fanspeeds(hass, caplog, mock_mirobo_fanspeeds):
    """Test Xiaomi vacuum fanspeeds."""
    entity_name = "test_vacuum_cleaner_2"
    entity_id = await setup_component(hass, entity_name)

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
    assert "Fan speed step not recognized" in caplog.text


async def setup_component(hass, entity_name):
    """Set up vacuum component."""
    entity_id = f"{DOMAIN}.{entity_name}"

    config_entry = MockConfigEntry(
        domain=XIAOMI_DOMAIN,
        unique_id="123456",
        title=entity_name,
        data={
            CONF_FLOW_TYPE: CONF_DEVICE,
            CONF_HOST: "192.168.1.100",
            CONF_TOKEN: "12345678901234567890123456789012",
            CONF_MODEL: MODELS_VACUUM[0],
            CONF_MAC: TEST_MAC,
        },
    )

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    return entity_id

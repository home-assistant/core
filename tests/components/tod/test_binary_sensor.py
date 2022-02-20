"""Test Times of the Day Binary Sensor."""
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from homeassistant.const import STATE_OFF, STATE_ON
import homeassistant.core as ha
from homeassistant.helpers.sun import get_astral_event_date, get_astral_event_next
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import assert_setup_component

ORIG_TIMEZONE = dt_util.DEFAULT_TIME_ZONE


@pytest.fixture(autouse=True)
def mock_legacy_time(legacy_patchable_time):
    """Make time patchable for all the tests."""
    yield


@pytest.fixture(autouse=True)
def setup_fixture(hass):
    """Set up things to be run when tests are started."""
    hass.config.latitude = 50.27583
    hass.config.longitude = 18.98583


@pytest.fixture(autouse=True)
def restore_timezone(hass):
    """Make sure we change timezone."""
    yield
    dt_util.set_default_time_zone(ORIG_TIMEZONE)


async def test_setup(hass):
    """Test the setup."""
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Early Morning",
                "after": "sunrise",
                "after_offset": "-02:00",
                "before": "7:00",
                "before_offset": "1:00",
            },
            {
                "platform": "tod",
                "name": "Morning",
                "after": "sunrise",
                "before": "12:00",
            },
        ]
    }
    with assert_setup_component(2):
        assert await async_setup_component(hass, "binary_sensor", config)


async def test_setup_no_sensors(hass):
    """Test setup with no sensors."""
    with assert_setup_component(0):
        assert await async_setup_component(
            hass, "binary_sensor", {"binary_sensor": {"platform": "tod"}}
        )


async def test_in_period_on_start(hass):
    """Test simple setting."""
    test_time = datetime(2019, 1, 10, 18, 43, 0, tzinfo=dt_util.UTC)
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Evening",
                "after": "18:00",
                "before": "22:00",
            }
        ]
    }
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=test_time,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.evening")
    assert state.state == STATE_ON


async def test_midnight_turnover_before_midnight_inside_period(hass):
    """Test midnight turnover setting before midnight inside period ."""
    test_time = datetime(2019, 1, 10, 22, 30, 0, tzinfo=dt_util.UTC)
    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Night", "after": "22:00", "before": "5:00"}
        ]
    }
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=test_time,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_ON


async def test_midnight_turnover_after_midnight_inside_period(hass):
    """Test midnight turnover setting before midnight inside period ."""
    test_time = datetime(2019, 1, 10, 21, 0, 0, tzinfo=dt_util.UTC)
    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Night", "after": "22:00", "before": "5:00"}
        ]
    }
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=test_time,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

        state = hass.states.get("binary_sensor.night")
        assert state.state == STATE_OFF

        await hass.async_block_till_done()

    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=test_time + timedelta(hours=1),
    ):

        hass.bus.async_fire(
            ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: test_time + timedelta(hours=1)}
        )

        await hass.async_block_till_done()
        state = hass.states.get("binary_sensor.night")
        assert state.state == STATE_ON


async def test_midnight_turnover_before_midnight_outside_period(hass):
    """Test midnight turnover setting before midnight outside period."""
    test_time = datetime(2019, 1, 10, 20, 30, 0, tzinfo=dt_util.UTC)
    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Night", "after": "22:00", "before": "5:00"}
        ]
    }
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=test_time,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_OFF


async def test_after_happens_tomorrow(hass):
    """Test when both before and after are in the future, and after is later than before."""
    test_time = datetime(2019, 1, 10, 10, 00, 0, tzinfo=dt_util.UTC)
    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Night", "after": "23:00", "before": "12:00"}
        ]
    }
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=test_time,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_ON


async def test_midnight_turnover_after_midnight_outside_period(hass):
    """Test midnight turnover setting before midnight inside period ."""
    test_time = datetime(2019, 1, 10, 20, 0, 0, tzinfo=dt_util.UTC)

    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Night", "after": "22:00", "before": "5:00"}
        ]
    }
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=test_time,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_OFF

    switchover_time = datetime(2019, 1, 11, 4, 59, 0, tzinfo=dt_util.UTC)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=switchover_time,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: switchover_time})
        await hass.async_block_till_done()
        state = hass.states.get("binary_sensor.night")
        assert state.state == STATE_ON

    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=switchover_time + timedelta(minutes=1, seconds=1),
    ):

        hass.bus.async_fire(
            ha.EVENT_TIME_CHANGED,
            {ha.ATTR_NOW: switchover_time + timedelta(minutes=1, seconds=1)},
        )

        await hass.async_block_till_done()
        state = hass.states.get("binary_sensor.night")
        assert state.state == STATE_OFF


async def test_from_sunrise_to_sunset(hass):
    """Test period from sunrise to sunset."""
    test_time = datetime(2019, 1, 12, tzinfo=dt_util.UTC)
    sunrise = dt_util.as_local(
        get_astral_event_date(hass, "sunrise", dt_util.as_utc(test_time))
    )
    sunset = dt_util.as_local(
        get_astral_event_date(hass, "sunset", dt_util.as_utc(test_time))
    )
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Day",
                "after": "sunrise",
                "before": "sunset",
            }
        ]
    }
    entity_id = "binary_sensor.day"
    testtime = sunrise + timedelta(seconds=-1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF

    testtime = sunrise
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    testtime = sunrise + timedelta(seconds=1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    await hass.async_block_till_done()

    testtime = sunset + timedelta(seconds=-1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    await hass.async_block_till_done()

    testtime = sunset
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF

    await hass.async_block_till_done()

    testtime = sunset + timedelta(seconds=1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF


async def test_from_sunset_to_sunrise(hass):
    """Test period from sunset to sunrise."""
    test_time = datetime(2019, 1, 12, tzinfo=dt_util.UTC)
    sunset = dt_util.as_local(get_astral_event_date(hass, "sunset", test_time))
    sunrise = dt_util.as_local(get_astral_event_next(hass, "sunrise", sunset))
    # assert sunset == sunrise
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Night",
                "after": "sunset",
                "before": "sunrise",
            }
        ]
    }
    entity_id = "binary_sensor.night"
    testtime = sunset + timedelta(minutes=-1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF

    testtime = sunset
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    testtime = sunset + timedelta(minutes=1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    testtime = sunrise + timedelta(minutes=-1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    testtime = sunrise
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        await hass.async_block_till_done()
        # assert state == "dupa"
        assert state.state == STATE_OFF

    testtime = sunrise + timedelta(minutes=1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF


async def test_offset(hass):
    """Test offset."""
    after = datetime(2019, 1, 10, 18, 0, 0, tzinfo=dt_util.UTC) + timedelta(
        hours=1, minutes=34
    )

    before = datetime(2019, 1, 10, 22, 0, 0, tzinfo=dt_util.UTC) + timedelta(
        hours=1, minutes=45
    )

    entity_id = "binary_sensor.evening"
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Evening",
                "after": "18:00",
                "after_offset": "1:34",
                "before": "22:00",
                "before_offset": "1:45",
            }
        ]
    }
    testtime = after + timedelta(seconds=-1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    testtime = after
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):
        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    testtime = before + timedelta(seconds=-1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):
        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    testtime = before
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):
        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF

    testtime = before + timedelta(seconds=1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):
        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF


async def test_offset_overnight(hass):
    """Test offset overnight."""
    after = datetime(2019, 1, 10, 18, 0, 0, tzinfo=dt_util.UTC) + timedelta(
        hours=1, minutes=34
    )
    entity_id = "binary_sensor.evening"
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Evening",
                "after": "18:00",
                "after_offset": "1:34",
                "before": "22:00",
                "before_offset": "3:00",
            }
        ]
    }
    testtime = after + timedelta(seconds=-1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    testtime = after
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):
        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON


async def test_norwegian_case_winter(hass):
    """Test location in Norway where the sun doesn't set in summer."""
    hass.config.latitude = 69.6
    hass.config.longitude = 18.8

    test_time = datetime(2010, 1, 1, tzinfo=dt_util.UTC)
    sunrise = dt_util.as_local(
        get_astral_event_next(hass, "sunrise", dt_util.as_utc(test_time))
    )
    sunset = dt_util.as_local(
        get_astral_event_next(hass, "sunset", dt_util.as_utc(test_time))
    )
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Day",
                "after": "sunrise",
                "before": "sunset",
            }
        ]
    }
    entity_id = "binary_sensor.day"
    testtime = test_time
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF

    testtime = sunrise + timedelta(seconds=-1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF

    testtime = sunrise
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    testtime = sunrise + timedelta(seconds=1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    await hass.async_block_till_done()

    testtime = sunset + timedelta(seconds=-1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    await hass.async_block_till_done()

    testtime = sunset
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF

    await hass.async_block_till_done()

    testtime = sunset + timedelta(seconds=1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF


async def test_norwegian_case_summer(hass):
    """Test location in Norway where the sun doesn't set in summer."""
    hass.config.latitude = 69.6
    hass.config.longitude = 18.8
    hass.config.elevation = 10.0

    test_time = datetime(2010, 6, 1, tzinfo=dt_util.UTC)

    sunrise = dt_util.as_local(
        get_astral_event_next(hass, "sunrise", dt_util.as_utc(test_time))
    )
    sunset = dt_util.as_local(
        get_astral_event_next(hass, "sunset", dt_util.as_utc(sunrise))
    )
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Day",
                "after": "sunrise",
                "before": "sunset",
            }
        ]
    }
    entity_id = "binary_sensor.day"
    testtime = test_time
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF

    testtime = sunrise + timedelta(seconds=-1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF

    testtime = sunrise
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    testtime = sunrise + timedelta(seconds=1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    await hass.async_block_till_done()

    testtime = sunset + timedelta(seconds=-1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    await hass.async_block_till_done()

    testtime = sunset
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF

    await hass.async_block_till_done()

    testtime = sunset + timedelta(seconds=1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF


async def test_sun_offset(hass):
    """Test sun event with offset."""
    test_time = datetime(2019, 1, 12, tzinfo=dt_util.UTC)
    sunrise = dt_util.as_local(
        get_astral_event_date(hass, "sunrise", dt_util.as_utc(test_time))
        + timedelta(hours=-1, minutes=-30)
    )
    sunset = dt_util.as_local(
        get_astral_event_date(hass, "sunset", dt_util.as_utc(test_time))
        + timedelta(hours=1, minutes=30)
    )
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Day",
                "after": "sunrise",
                "after_offset": "-1:30",
                "before": "sunset",
                "before_offset": "1:30",
            }
        ]
    }
    entity_id = "binary_sensor.day"
    testtime = sunrise + timedelta(seconds=-1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF

    testtime = sunrise
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    testtime = sunrise + timedelta(seconds=1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    await hass.async_block_till_done()

    testtime = sunset + timedelta(seconds=-1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON

    await hass.async_block_till_done()

    testtime = sunset
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF

    await hass.async_block_till_done()

    testtime = sunset + timedelta(seconds=1)
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_OFF

    test_time = test_time + timedelta(days=1)
    sunrise = dt_util.as_local(
        get_astral_event_date(hass, "sunrise", dt_util.as_utc(test_time))
        + timedelta(hours=-1, minutes=-30)
    )
    testtime = sunrise
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=testtime,
    ):

        hass.bus.async_fire(ha.EVENT_TIME_CHANGED, {ha.ATTR_NOW: testtime})
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state.state == STATE_ON


async def test_dst(hass):
    """Test sun event with offset."""
    hass.config.time_zone = "CET"
    dt_util.set_default_time_zone(dt_util.get_time_zone("CET"))
    test_time = datetime(2019, 3, 30, 3, 0, 0, tzinfo=dt_util.UTC)
    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Day", "after": "2:30", "before": "2:40"}
        ]
    }
    # Test DST:
    # after 2019-03-30 03:00 CET the next update should ge scheduled
    # at 3:30 not 2:30 local time
    entity_id = "binary_sensor.day"
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=test_time,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

        await hass.async_block_till_done()
        state = hass.states.get(entity_id)
        assert state.attributes["after"] == "2019-03-31T03:30:00+02:00"
        assert state.attributes["before"] == "2019-03-31T03:40:00+02:00"
        assert state.attributes["next_update"] == "2019-03-31T03:30:00+02:00"
        assert state.state == STATE_OFF


async def test_simple_before_after_does_not_loop_utc_not_in_range(hass):
    """Test simple before after."""
    hass.config.time_zone = "UTC"
    dt_util.set_default_time_zone(dt_util.UTC)
    test_time = datetime(2019, 1, 10, 18, 43, 0, tzinfo=dt_util.UTC)
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Night",
                "before": "06:00",
                "after": "22:00",
            }
        ]
    }
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=test_time,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_OFF
    assert state.attributes["after"] == "2019-01-10T22:00:00+00:00"
    assert state.attributes["before"] == "2019-01-11T06:00:00+00:00"
    assert state.attributes["next_update"] == "2019-01-10T22:00:00+00:00"


async def test_simple_before_after_does_not_loop_utc_in_range(hass):
    """Test simple before after."""
    hass.config.time_zone = "UTC"
    dt_util.set_default_time_zone(dt_util.UTC)
    test_time = datetime(2019, 1, 10, 22, 43, 0, tzinfo=dt_util.UTC)
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Night",
                "before": "06:00",
                "after": "22:00",
            }
        ]
    }
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=test_time,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_ON
    assert state.attributes["after"] == "2019-01-10T22:00:00+00:00"
    assert state.attributes["before"] == "2019-01-11T06:00:00+00:00"
    assert state.attributes["next_update"] == "2019-01-11T06:00:00+00:00"


async def test_simple_before_after_does_not_loop_utc_fire_at_before(hass):
    """Test simple before after."""
    hass.config.time_zone = "UTC"
    dt_util.set_default_time_zone(dt_util.UTC)
    test_time = datetime(2019, 1, 11, 6, 0, 0, tzinfo=dt_util.UTC)
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Night",
                "before": "06:00",
                "after": "22:00",
            }
        ]
    }
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=test_time,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_OFF
    assert state.attributes["after"] == "2019-01-11T22:00:00+00:00"
    assert state.attributes["before"] == "2019-01-12T06:00:00+00:00"
    assert state.attributes["next_update"] == "2019-01-11T22:00:00+00:00"


async def test_simple_before_after_does_not_loop_utc_fire_at_after(hass):
    """Test simple before after."""
    hass.config.time_zone = "UTC"
    dt_util.set_default_time_zone(dt_util.UTC)
    test_time = datetime(2019, 1, 10, 22, 0, 0, tzinfo=dt_util.UTC)
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Night",
                "before": "06:00",
                "after": "22:00",
            }
        ]
    }
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=test_time,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_ON
    assert state.attributes["after"] == "2019-01-10T22:00:00+00:00"
    assert state.attributes["before"] == "2019-01-11T06:00:00+00:00"
    assert state.attributes["next_update"] == "2019-01-11T06:00:00+00:00"


async def test_simple_before_after_does_not_loop_utc_both_before_now(hass):
    """Test simple before after."""
    hass.config.time_zone = "UTC"
    dt_util.set_default_time_zone(dt_util.UTC)
    test_time = datetime(2019, 1, 10, 22, 0, 0, tzinfo=dt_util.UTC)
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Morning",
                "before": "08:00",
                "after": "00:00",
            }
        ]
    }
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=test_time,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.morning")
    assert state.state == STATE_OFF
    assert state.attributes["after"] == "2019-01-11T00:00:00+00:00"
    assert state.attributes["before"] == "2019-01-11T08:00:00+00:00"
    assert state.attributes["next_update"] == "2019-01-11T00:00:00+00:00"


async def test_simple_before_after_does_not_loop_berlin_not_in_range(hass):
    """Test simple before after."""
    hass.config.time_zone = "Europe/Berlin"
    dt_util.set_default_time_zone(dt_util.get_time_zone("Europe/Berlin"))
    test_time = datetime(2019, 1, 10, 18, 43, 0, tzinfo=dt_util.UTC)
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Dark",
                "before": "06:00",
                "after": "00:00",
            }
        ]
    }
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=test_time,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.dark")
    assert state.state == STATE_OFF
    assert state.attributes["after"] == "2019-01-11T00:00:00+01:00"
    assert state.attributes["before"] == "2019-01-11T06:00:00+01:00"
    assert state.attributes["next_update"] == "2019-01-11T00:00:00+01:00"


async def test_simple_before_after_does_not_loop_berlin_in_range(hass):
    """Test simple before after."""
    hass.config.time_zone = "Europe/Berlin"
    dt_util.set_default_time_zone(dt_util.get_time_zone("Europe/Berlin"))
    test_time = datetime(2019, 1, 10, 23, 43, 0, tzinfo=dt_util.UTC)
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Dark",
                "before": "06:00",
                "after": "00:00",
            }
        ]
    }
    with patch(
        "homeassistant.components.tod.binary_sensor.dt_util.utcnow",
        return_value=test_time,
    ):
        await async_setup_component(hass, "binary_sensor", config)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.dark")
    assert state.state == STATE_ON
    assert state.attributes["after"] == "2019-01-11T00:00:00+01:00"
    assert state.attributes["before"] == "2019-01-11T06:00:00+01:00"
    assert state.attributes["next_update"] == "2019-01-11T06:00:00+01:00"

"""Test Times of the Day Binary Sensor."""
from datetime import datetime, timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
import homeassistant.helpers.entity_registry as er
from homeassistant.helpers.sun import get_astral_event_date, get_astral_event_next
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import assert_setup_component, async_fire_time_changed


@pytest.fixture
def hass_time_zone():
    """Return default hass timezone."""
    return "US/Pacific"


@pytest.fixture(autouse=True)
def setup_fixture(hass, hass_time_zone):
    """Set up things to be run when tests are started."""
    hass.config.latitude = 50.27583
    hass.config.longitude = 18.98583
    hass.config.set_time_zone(hass_time_zone)


@pytest.fixture
def hass_tz_info(hass):
    """Return timezone info for the hass timezone."""
    return dt_util.get_time_zone(hass.config.time_zone)


async def test_setup(hass: HomeAssistant) -> None:
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


async def test_setup_no_sensors(hass: HomeAssistant) -> None:
    """Test setup with no sensors."""
    with assert_setup_component(0):
        assert await async_setup_component(
            hass, "binary_sensor", {"binary_sensor": {"platform": "tod"}}
        )


@pytest.mark.freeze_time("2019-01-10 18:43:00-08:00")
async def test_in_period_on_start(hass: HomeAssistant) -> None:
    """Test simple setting."""
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
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.evening")
    assert state.state == STATE_ON


@pytest.mark.freeze_time("2019-01-10 22:30:00-08:00")
async def test_midnight_turnover_before_midnight_inside_period(
    hass: HomeAssistant,
) -> None:
    """Test midnight turnover setting before midnight inside period ."""
    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Night", "after": "22:00", "before": "5:00"}
        ]
    }
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_ON


async def test_midnight_turnover_after_midnight_inside_period(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test midnight turnover setting before midnight inside period ."""
    test_time = datetime(2019, 1, 10, 21, 0, 0, tzinfo=hass_tz_info)
    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Night", "after": "22:00", "before": "5:00"}
        ]
    }
    freezer.move_to(test_time)
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_OFF

    await hass.async_block_till_done()

    freezer.move_to(test_time + timedelta(hours=1))
    async_fire_time_changed(hass, dt_util.utcnow())

    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_ON


@pytest.mark.freeze_time("2019-01-10 20:30:00-08:00")
async def test_midnight_turnover_before_midnight_outside_period(
    hass: HomeAssistant,
) -> None:
    """Test midnight turnover setting before midnight outside period."""
    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Night", "after": "22:00", "before": "5:00"}
        ]
    }
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_OFF


@pytest.mark.freeze_time("2019-01-10 10:00:00-08:00")
async def test_after_happens_tomorrow(hass: HomeAssistant) -> None:
    """Test when both before and after are in the future, and after is later than before."""
    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Night", "after": "23:00", "before": "12:00"}
        ]
    }
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_ON


async def test_midnight_turnover_after_midnight_outside_period(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test midnight turnover setting before midnight inside period ."""
    test_time = datetime(2019, 1, 10, 20, 0, 0, tzinfo=hass_tz_info)

    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Night", "after": "22:00", "before": "5:00"}
        ]
    }
    freezer.move_to(test_time)
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_OFF

    switchover_time = datetime(2019, 1, 11, 4, 59, 0, tzinfo=hass_tz_info)
    freezer.move_to(switchover_time)

    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_ON

    freezer.move_to(switchover_time + timedelta(minutes=1, seconds=1))

    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_OFF


async def test_from_sunrise_to_sunset(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test period from sunrise to sunset."""
    test_time = datetime(2019, 1, 12, tzinfo=hass_tz_info)
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
    freezer.move_to(sunrise + timedelta(seconds=-1))
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    freezer.move_to(sunrise)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    freezer.move_to(sunrise + timedelta(seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    freezer.move_to(sunset + timedelta(seconds=-1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    freezer.move_to(sunset)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    freezer.move_to(sunset + timedelta(seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_from_sunset_to_sunrise(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test period from sunset to sunrise."""
    test_time = datetime(2019, 1, 12, tzinfo=hass_tz_info)
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
    freezer.move_to(sunset + timedelta(seconds=-1))
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    freezer.move_to(sunset)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    freezer.move_to(sunset + timedelta(minutes=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    freezer.move_to(sunrise + timedelta(minutes=-1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    freezer.move_to(sunrise)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    freezer.move_to(sunrise + timedelta(minutes=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_offset(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test offset."""
    after = datetime(2019, 1, 10, 18, 0, 0, tzinfo=hass_tz_info) + timedelta(
        hours=1, minutes=34
    )

    before = datetime(2019, 1, 10, 22, 0, 0, tzinfo=hass_tz_info) + timedelta(
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
    freezer.move_to(after + timedelta(seconds=-1))
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    freezer.move_to(after)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    freezer.move_to(before + timedelta(seconds=-1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    freezer.move_to(before)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    freezer.move_to(before + timedelta(seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_offset_overnight(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test offset overnight."""
    after = datetime(2019, 1, 10, 18, 0, 0, tzinfo=hass_tz_info) + timedelta(
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
    freezer.move_to(after + timedelta(seconds=-1))
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    freezer.move_to(after)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_norwegian_case_winter(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test location in Norway where the sun doesn't set in summer."""
    hass.config.latitude = 69.6
    hass.config.longitude = 18.8

    test_time = datetime(2010, 1, 1, tzinfo=hass_tz_info)
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
    freezer.move_to(test_time)
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    freezer.move_to(sunrise + timedelta(seconds=-1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    freezer.move_to(sunrise)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    freezer.move_to(sunrise + timedelta(seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    freezer.move_to(sunset + timedelta(seconds=-1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    freezer.move_to(sunset)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    freezer.move_to(sunset + timedelta(seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_norwegian_case_summer(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test location in Norway where the sun doesn't set in summer."""
    hass.config.latitude = 69.6
    hass.config.longitude = 18.8
    hass.config.elevation = 10.0

    test_time = datetime(2010, 6, 1, tzinfo=hass_tz_info)

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
    freezer.move_to(test_time)
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    freezer.move_to(sunrise + timedelta(seconds=-1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    freezer.move_to(sunrise)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    freezer.move_to(sunrise + timedelta(seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    freezer.move_to(sunset + timedelta(seconds=-1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    freezer.move_to(sunset)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    freezer.move_to(sunset + timedelta(seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF


async def test_sun_offset(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test sun event with offset."""
    test_time = datetime(2019, 1, 12, tzinfo=hass_tz_info)
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
    freezer.move_to(sunrise + timedelta(seconds=-1))
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    freezer.move_to(sunrise)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    freezer.move_to(sunrise + timedelta(seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    freezer.move_to(sunset + timedelta(seconds=-1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON

    await hass.async_block_till_done()

    freezer.move_to(sunset)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    freezer.move_to(sunset + timedelta(seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_OFF

    test_time = test_time + timedelta(days=1)
    sunrise = dt_util.as_local(
        get_astral_event_date(hass, "sunrise", dt_util.as_utc(test_time))
        + timedelta(hours=-1, minutes=-30)
    )
    freezer.move_to(sunrise)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_ON


async def test_dst(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test sun event with offset."""
    hass.config.time_zone = "CET"
    dt_util.set_default_time_zone(dt_util.get_time_zone("CET"))
    test_time = datetime(2019, 3, 30, 3, 0, 0, tzinfo=hass_tz_info)
    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Day", "after": "2:30", "before": "2:40"}
        ]
    }
    # Test DST:
    # after 2019-03-30 03:00 CET the next update should ge scheduled
    # at 3:30 not 2:30 local time
    entity_id = "binary_sensor.day"
    freezer.move_to(test_time)
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["after"] == "2019-03-31T03:30:00+02:00"
    assert state.attributes["before"] == "2019-03-31T03:40:00+02:00"
    assert state.attributes["next_update"] == "2019-03-31T03:30:00+02:00"
    assert state.state == STATE_OFF


@pytest.mark.freeze_time("2019-01-10 18:43:00")
@pytest.mark.parametrize("hass_time_zone", ("UTC",))
async def test_simple_before_after_does_not_loop_utc_not_in_range(
    hass: HomeAssistant,
) -> None:
    """Test simple before after."""
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
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_OFF
    assert state.attributes["after"] == "2019-01-10T22:00:00+00:00"
    assert state.attributes["before"] == "2019-01-11T06:00:00+00:00"
    assert state.attributes["next_update"] == "2019-01-10T22:00:00+00:00"


@pytest.mark.freeze_time("2019-01-10 22:43:00")
@pytest.mark.parametrize("hass_time_zone", ("UTC",))
async def test_simple_before_after_does_not_loop_utc_in_range(
    hass: HomeAssistant,
) -> None:
    """Test simple before after."""
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
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_ON
    assert state.attributes["after"] == "2019-01-10T22:00:00+00:00"
    assert state.attributes["before"] == "2019-01-11T06:00:00+00:00"
    assert state.attributes["next_update"] == "2019-01-11T06:00:00+00:00"


@pytest.mark.freeze_time("2019-01-11 06:00:00")
@pytest.mark.parametrize("hass_time_zone", ("UTC",))
async def test_simple_before_after_does_not_loop_utc_fire_at_before(
    hass: HomeAssistant,
) -> None:
    """Test simple before after."""
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
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_OFF
    assert state.attributes["after"] == "2019-01-11T22:00:00+00:00"
    assert state.attributes["before"] == "2019-01-12T06:00:00+00:00"
    assert state.attributes["next_update"] == "2019-01-11T22:00:00+00:00"


@pytest.mark.freeze_time("2019-01-10 22:00:00")
@pytest.mark.parametrize("hass_time_zone", ("UTC",))
async def test_simple_before_after_does_not_loop_utc_fire_at_after(
    hass: HomeAssistant,
) -> None:
    """Test simple before after."""
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
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_ON
    assert state.attributes["after"] == "2019-01-10T22:00:00+00:00"
    assert state.attributes["before"] == "2019-01-11T06:00:00+00:00"
    assert state.attributes["next_update"] == "2019-01-11T06:00:00+00:00"


@pytest.mark.freeze_time("2019-01-10 22:00:00")
@pytest.mark.parametrize("hass_time_zone", ("UTC",))
async def test_simple_before_after_does_not_loop_utc_both_before_now(
    hass: HomeAssistant,
) -> None:
    """Test simple before after."""
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
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.morning")
    assert state.state == STATE_OFF
    assert state.attributes["after"] == "2019-01-11T00:00:00+00:00"
    assert state.attributes["before"] == "2019-01-11T08:00:00+00:00"
    assert state.attributes["next_update"] == "2019-01-11T00:00:00+00:00"


@pytest.mark.freeze_time("2019-01-10 17:43:00+01:00")
@pytest.mark.parametrize("hass_time_zone", ("Europe/Berlin",))
async def test_simple_before_after_does_not_loop_berlin_not_in_range(
    hass: HomeAssistant,
) -> None:
    """Test simple before after."""
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
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.dark")
    assert state.state == STATE_OFF
    assert state.attributes["after"] == "2019-01-11T00:00:00+01:00"
    assert state.attributes["before"] == "2019-01-11T06:00:00+01:00"
    assert state.attributes["next_update"] == "2019-01-11T00:00:00+01:00"


@pytest.mark.freeze_time("2019-01-11 00:43:00+01:00")
@pytest.mark.parametrize("hass_time_zone", ("Europe/Berlin",))
async def test_simple_before_after_does_not_loop_berlin_in_range(
    hass: HomeAssistant,
) -> None:
    """Test simple before after."""
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
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.dark")
    assert state.state == STATE_ON
    assert state.attributes["after"] == "2019-01-11T00:00:00+01:00"
    assert state.attributes["before"] == "2019-01-11T06:00:00+01:00"
    assert state.attributes["next_update"] == "2019-01-11T06:00:00+01:00"


async def test_unique_id(hass: HomeAssistant) -> None:
    """Test unique id."""
    config = {
        "binary_sensor": [
            {
                "platform": "tod",
                "name": "Evening",
                "after": "18:00",
                "before": "22:00",
                "unique_id": "very_unique_id",
            }
        ]
    }
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    entity_reg = er.async_get(hass)
    entity = entity_reg.async_get("binary_sensor.evening")

    assert entity.unique_id == "very_unique_id"

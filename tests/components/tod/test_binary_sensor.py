"""Test Times of the Day Binary Sensor."""

from datetime import datetime, timedelta, tzinfo

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.sun import get_astral_event_date, get_astral_event_next
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import assert_setup_component, async_fire_time_changed


@pytest.fixture
def hass_time_zone() -> str:
    """Return default hass timezone."""
    return "US/Pacific"


@pytest.fixture(autouse=True)
async def setup_fixture(hass: HomeAssistant, hass_time_zone: str) -> None:
    """Set up things to be run when tests are started."""
    hass.config.latitude = 50.27583
    hass.config.longitude = 18.98583
    await hass.config.async_set_time_zone(hass_time_zone)


@pytest.fixture
def hass_tz_info(hass: HomeAssistant) -> tzinfo | None:
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
    """Test when before and after are in the future, after is later than before."""
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


async def test_fixed_time_offsets_next_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_tz_info: tzinfo | None,
) -> None:
    """Test fixed-time offsets remain applied on the next day."""
    after = datetime(2019, 1, 10, 10, 30, tzinfo=hass_tz_info)
    before = datetime(2019, 1, 10, 18, 45, tzinfo=hass_tz_info)
    freezer.move_to(after - timedelta(seconds=1))
    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": [
                {
                    "platform": "tod",
                    "name": "Daytime",
                    "after": "10:00",
                    "after_offset": "0:30",
                    "before": "18:00",
                    "before_offset": "0:45",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    freezer.move_to(after)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.daytime").state == STATE_ON

    freezer.move_to(before)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.daytime").state == STATE_OFF

    next_after = after + timedelta(days=1)
    freezer.move_to(next_after - timedelta(seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.daytime")
    assert state.state == STATE_OFF
    assert state.attributes["after"] == next_after.isoformat()

    freezer.move_to(next_after)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.daytime").state == STATE_ON

    next_before = before + timedelta(days=1)
    freezer.move_to(next_before - timedelta(seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.daytime")
    assert state.state == STATE_ON
    assert state.attributes["before"] == next_before.isoformat()

    freezer.move_to(next_before)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.daytime").state == STATE_OFF


@pytest.mark.parametrize(
    ("config", "after", "before", "next_after", "next_before"),
    [
        pytest.param(
            {
                "after": "23:30",
                "after_offset": "1:00",
                "before": "02:00",
            },
            "2019-01-11T00:30",
            "2019-01-11T02:00",
            "2019-01-12T00:30",
            "2019-01-12T02:00",
            id="after-offset-crosses-midnight",
        ),
        pytest.param(
            {
                "after": "20:00",
                "before": "00:30",
                "before_offset": "-1:00",
            },
            "2019-01-10T20:00",
            "2019-01-10T23:30",
            "2019-01-11T20:00",
            "2019-01-11T23:30",
            id="before-offset-crosses-midnight",
        ),
    ],
)
async def test_fixed_time_offsets_crossing_midnight_next_day(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_tz_info: tzinfo | None,
    config: dict[str, str],
    after: str,
    before: str,
    next_after: str,
    next_before: str,
) -> None:
    """Test next-day rollover uses unoffset fixed-time boundaries."""
    after_time = datetime.fromisoformat(after).replace(tzinfo=hass_tz_info)
    before_time = datetime.fromisoformat(before).replace(tzinfo=hass_tz_info)
    freezer.move_to(after_time)
    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": [
                {
                    "platform": "tod",
                    "name": "Offset interval",
                    **config,
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.offset_interval").state == STATE_ON

    freezer.move_to(before_time)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.offset_interval")
    assert state.state == STATE_OFF
    assert (
        state.attributes["after"]
        == datetime.fromisoformat(next_after).replace(tzinfo=hass_tz_info).isoformat()
    )
    assert (
        state.attributes["before"]
        == datetime.fromisoformat(next_before).replace(tzinfo=hass_tz_info).isoformat()
    )


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


async def test_offset_overnight_restart(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_tz_info: tzinfo | None,
) -> None:
    """Test initialization during an offset-created overnight interval."""
    after = datetime(2019, 1, 10, 19, 34, tzinfo=hass_tz_info)
    before = datetime(2019, 1, 11, 1, tzinfo=hass_tz_info)
    freezer.move_to(datetime(2019, 1, 11, 0, 30, tzinfo=hass_tz_info))
    await async_setup_component(
        hass,
        "binary_sensor",
        {
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
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.evening")
    assert state.state == STATE_ON
    assert state.attributes["after"] == after.isoformat()
    assert state.attributes["before"] == before.isoformat()

    freezer.move_to(before)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.evening")
    assert state.state == STATE_OFF


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


async def test_sun_offsets_cross_boundary(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_tz_info: tzinfo | None,
) -> None:
    """Test sun offsets that move the effective before boundary to the next day."""
    test_time = datetime(2019, 1, 12, tzinfo=hass_tz_info)
    after_offset = timedelta(hours=13)
    before_offset = timedelta(minutes=30)
    after = (
        get_astral_event_date(hass, "sunrise", dt_util.as_utc(test_time)) + after_offset
    )
    before = (
        get_astral_event_next(hass, "sunset", after - before_offset) + before_offset
    )
    freezer.move_to(after)
    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": [
                {
                    "platform": "tod",
                    "name": "Overnight sun",
                    "after": "sunrise",
                    "after_offset": "13:00",
                    "before": "sunset",
                    "before_offset": "0:30",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.overnight_sun")
    assert state.state == STATE_ON
    assert state.attributes["after"] == after.astimezone(hass_tz_info).isoformat()
    assert state.attributes["before"] == before.astimezone(hass_tz_info).isoformat()

    freezer.move_to(before)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.overnight_sun")
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    (
        "after_event",
        "after_offset_config",
        "after_offset",
        "before_event",
        "before_offset_config",
        "before_offset",
    ),
    [
        pytest.param(
            "sunset",
            "0:00",
            timedelta(0),
            "sunrise",
            "0:00",
            timedelta(0),
            id="sunset-to-sunrise",
        ),
        pytest.param(
            "sunrise",
            "13:00",
            timedelta(hours=13),
            "sunset",
            "0:30",
            timedelta(minutes=30),
            id="offset-crossing",
        ),
    ],
)
async def test_sun_interval_restart(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_tz_info: tzinfo | None,
    after_event: str,
    after_offset_config: str,
    after_offset: timedelta,
    before_event: str,
    before_offset_config: str,
    before_offset: timedelta,
) -> None:
    """Test initialization during the previous solar interval."""
    test_time = datetime(2019, 1, 13, tzinfo=hass_tz_info)
    after = (
        get_astral_event_date(hass, after_event, test_time - timedelta(days=1))
        + after_offset
    )
    before = get_astral_event_date(hass, before_event, test_time) + before_offset
    freezer.move_to(before - timedelta(minutes=1))

    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": [
                {
                    "platform": "tod",
                    "name": "Solar interval",
                    "after": after_event,
                    "after_offset": after_offset_config,
                    "before": before_event,
                    "before_offset": before_offset_config,
                }
            ]
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.solar_interval")
    assert state.state == STATE_ON
    assert state.attributes["after"] == after.astimezone(hass_tz_info).isoformat()
    assert state.attributes["before"] == before.astimezone(hass_tz_info).isoformat()


async def test_sun_to_fixed_time_interval_restart(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_tz_info: tzinfo | None,
) -> None:
    """Test initialization during a solar-to-fixed-time interval."""
    restart_time = datetime(2019, 1, 13, 6, tzinfo=hass_tz_info)
    after = get_astral_event_date(hass, "sunset", restart_time - timedelta(days=1))
    before = datetime(2019, 1, 13, 7, tzinfo=hass_tz_info)
    freezer.move_to(restart_time)

    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": [
                {
                    "platform": "tod",
                    "name": "Night",
                    "after": "sunset",
                    "before": "07:00",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_ON
    assert state.attributes["after"] == after.astimezone(hass_tz_info).isoformat()
    assert state.attributes["before"] == before.isoformat()

    freezer.move_to(before)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_OFF


async def test_fixed_time_to_sun_interval_restart_across_dst(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test fixed-to-solar interval initialization across DST."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    time_zone = dt_util.get_time_zone(hass.config.time_zone)
    test_date = datetime(2019, 3, 31, tzinfo=time_zone)
    after = datetime(2019, 3, 30, 20, tzinfo=time_zone)
    before = get_astral_event_date(hass, "sunrise", test_date)
    freezer.move_to(before - timedelta(minutes=30))

    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": [
                {
                    "platform": "tod",
                    "name": "Night",
                    "after": "20:00",
                    "before": "sunrise",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_ON
    assert state.attributes["after"] == after.isoformat()
    assert state.attributes["before"] == before.astimezone(time_zone).isoformat()

    freezer.move_to(before)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_OFF


async def test_fixed_overnight_interval_across_dst(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a fixed overnight interval ends at the configured time across DST."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    time_zone = dt_util.get_time_zone(hass.config.time_zone)
    after = datetime(2019, 3, 30, 20, tzinfo=time_zone)
    before = datetime(2019, 3, 31, 7, tzinfo=time_zone)
    freezer.move_to(after)

    await async_setup_component(
        hass,
        "binary_sensor",
        {
            "binary_sensor": [
                {
                    "platform": "tod",
                    "name": "Night",
                    "after": "20:00",
                    "before": "07:00",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.night")
    assert state.state == STATE_ON
    assert state.attributes["after"] == after.isoformat()
    assert state.attributes["before"] == before.isoformat()

    freezer.move_to(before - timedelta(seconds=1))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.night").state == STATE_ON

    freezer.move_to(before)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.night").state == STATE_OFF


async def test_dst1(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test DST when time falls in non-existent hour. Also check 48 hours later."""
    hass.config.time_zone = "CET"
    dt_util.set_default_time_zone(dt_util.get_time_zone("CET"))
    test_time1 = datetime(2019, 3, 30, 3, 0, 0, tzinfo=dt_util.get_time_zone("CET"))
    test_time2 = datetime(2019, 3, 31, 3, 0, 0, tzinfo=dt_util.get_time_zone("CET"))
    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Day", "after": "2:30", "before": "2:40"}
        ]
    }
    # Test DST #1:
    # after 2019-03-30 03:00 CET the next update should ge scheduled
    # at 2:30am, but on 2019-03-31, that hour does not exist.  That means
    # the start/end will end up happning on the next available second (3am)
    # Essentially, the ToD sensor never turns on that day.
    entity_id = "binary_sensor.day"
    freezer.move_to(test_time1)
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["after"] == "2019-03-31T03:00:00+02:00"
    assert state.attributes["before"] == "2019-03-31T03:00:00+02:00"
    assert state.attributes["next_update"] == "2019-03-31T03:00:00+02:00"
    assert state.state == STATE_OFF

    # But the following day, the sensor should resume it normal operation.
    freezer.move_to(test_time2)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["after"] == "2019-04-01T02:30:00+02:00"
    assert state.attributes["before"] == "2019-04-01T02:40:00+02:00"
    assert state.attributes["next_update"] == "2019-04-01T02:30:00+02:00"

    assert state.state == STATE_OFF


async def test_dst2(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test DST when there's a time switch in the East."""
    hass.config.time_zone = "CET"
    dt_util.set_default_time_zone(dt_util.get_time_zone("CET"))
    test_time = datetime(2019, 3, 30, 5, 0, 0, tzinfo=dt_util.get_time_zone("CET"))
    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Day", "after": "4:30", "before": "4:40"}
        ]
    }
    # Test DST #2:
    # after 2019-03-30 05:00 CET the next update should ge scheduled
    # at 4:30+02 not 4:30+01
    entity_id = "binary_sensor.day"
    freezer.move_to(test_time)
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["after"] == "2019-03-31T04:30:00+02:00"
    assert state.attributes["before"] == "2019-03-31T04:40:00+02:00"
    assert state.attributes["next_update"] == "2019-03-31T04:30:00+02:00"
    assert state.state == STATE_OFF


async def test_dst3(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test DST when there's a time switch forward in the West."""
    hass.config.time_zone = "US/Pacific"
    dt_util.set_default_time_zone(dt_util.get_time_zone("US/Pacific"))
    test_time = datetime(
        2023, 3, 11, 5, 0, 0, tzinfo=dt_util.get_time_zone("US/Pacific")
    )
    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Day", "after": "4:30", "before": "4:40"}
        ]
    }
    # Test DST #3:
    # after 2023-03-11 05:00 Pacific the next update should ge scheduled
    # at 4:30-07 not 4:30-08
    entity_id = "binary_sensor.day"
    freezer.move_to(test_time)
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["after"] == "2023-03-12T04:30:00-07:00"
    assert state.attributes["before"] == "2023-03-12T04:40:00-07:00"
    assert state.attributes["next_update"] == "2023-03-12T04:30:00-07:00"
    assert state.state == STATE_OFF


async def test_dst4(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test DST when there's a time switch backward in the West."""
    hass.config.time_zone = "US/Pacific"
    dt_util.set_default_time_zone(dt_util.get_time_zone("US/Pacific"))
    test_time = datetime(
        2023, 11, 4, 5, 0, 0, tzinfo=dt_util.get_time_zone("US/Pacific")
    )
    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Day", "after": "4:30", "before": "4:40"}
        ]
    }
    # Test DST #4:
    # after 2023-11-04 05:00 Pacific the next update should ge scheduled
    # at 4:30-08 not 4:30-07
    entity_id = "binary_sensor.day"
    freezer.move_to(test_time)
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["after"] == "2023-11-05T04:30:00-08:00"
    assert state.attributes["before"] == "2023-11-05T04:40:00-08:00"
    assert state.attributes["next_update"] == "2023-11-05T04:30:00-08:00"
    assert state.state == STATE_OFF


async def test_dst5(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test DST when end time falls in non-existent hour (1:50am-2:10am)."""
    hass.config.time_zone = "CET"
    dt_util.set_default_time_zone(dt_util.get_time_zone("CET"))
    test_time1 = datetime(2019, 3, 30, 3, 0, 0, tzinfo=dt_util.get_time_zone("CET"))
    test_time2 = datetime(2019, 3, 31, 1, 51, 0, tzinfo=dt_util.get_time_zone("CET"))
    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Day", "after": "1:50", "before": "2:10"}
        ]
    }
    # Test DST #5:
    # Test case where end time does not exist
    # (roll out to the next available time)
    # First test before the sensor is turned on
    entity_id = "binary_sensor.day"
    freezer.move_to(test_time1)
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["after"] == "2019-03-31T01:50:00+01:00"
    assert state.attributes["before"] == "2019-03-31T03:00:00+02:00"
    assert state.attributes["next_update"] == "2019-03-31T01:50:00+01:00"
    assert state.state == STATE_OFF

    # Second, test state when sensor is ON but end time has rolled
    # out to next available time.
    freezer.move_to(test_time2)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["after"] == "2019-03-31T01:50:00+01:00"
    assert state.attributes["before"] == "2019-03-31T03:00:00+02:00"
    assert state.attributes["next_update"] == "2019-03-31T03:00:00+02:00"

    assert state.state == STATE_ON


async def test_dst6(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, hass_tz_info
) -> None:
    """Test DST when start time falls in non-existent hour (2:50am 3:10am)."""
    hass.config.time_zone = "CET"
    dt_util.set_default_time_zone(dt_util.get_time_zone("CET"))
    test_time1 = datetime(2019, 3, 30, 4, 0, 0, tzinfo=dt_util.get_time_zone("CET"))
    test_time2 = datetime(2019, 3, 31, 3, 1, 0, tzinfo=dt_util.get_time_zone("CET"))
    config = {
        "binary_sensor": [
            {"platform": "tod", "name": "Day", "after": "2:50", "before": "3:10"}
        ]
    }
    # Test DST #6:
    # Test case where end time does not exist
    # (roll out to the next available time)
    # First test before the sensor is turned on
    entity_id = "binary_sensor.day"
    freezer.move_to(test_time1)
    await async_setup_component(hass, "binary_sensor", config)
    await hass.async_block_till_done()

    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.attributes["after"] == "2019-03-31T03:00:00+02:00"
    assert state.attributes["before"] == "2019-03-31T03:10:00+02:00"
    assert state.attributes["next_update"] == "2019-03-31T03:00:00+02:00"
    assert state.state == STATE_OFF

    # Second, test state when sensor is ON but end time has rolled
    # out to next available time.
    freezer.move_to(test_time2)
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.attributes["after"] == "2019-03-31T03:00:00+02:00"
    assert state.attributes["before"] == "2019-03-31T03:10:00+02:00"
    assert state.attributes["next_update"] == "2019-03-31T03:10:00+02:00"

    assert state.state == STATE_ON


@pytest.mark.freeze_time("2019-01-10 18:43:00")
@pytest.mark.parametrize("hass_time_zone", ["UTC"])
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
@pytest.mark.parametrize("hass_time_zone", ["UTC"])
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
@pytest.mark.parametrize("hass_time_zone", ["UTC"])
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
@pytest.mark.parametrize("hass_time_zone", ["UTC"])
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
@pytest.mark.parametrize("hass_time_zone", ["UTC"])
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
@pytest.mark.parametrize("hass_time_zone", ["Europe/Berlin"])
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
@pytest.mark.parametrize("hass_time_zone", ["Europe/Berlin"])
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


async def test_unique_id(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
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

    entity = entity_registry.async_get("binary_sensor.evening")

    assert entity.unique_id == "very_unique_id"

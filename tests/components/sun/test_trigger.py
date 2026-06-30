"""The tests for the sun automation."""

from datetime import datetime, timedelta
from typing import Any

from astral.sun import elevation as astral_elevation
from freezegun import freeze_time
import pytest
import voluptuous as vol

from homeassistant.components import automation, sun
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SUN_EVENT_SUNRISE,
    SUN_EVENT_SUNSET,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.sun import (
    get_astral_event_next,
    get_astral_observer,
    get_observer_astral_event_next,
)
from homeassistant.helpers.trigger import async_validate_trigger_config
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed, mock_component
from tests.components.common import assert_trigger_options_supported

_TEST_DATETIME = datetime(2015, 9, 15, 1, tzinfo=dt_util.UTC)
_SUN_ENTITY_ID = "sun.sun"

# Next dawn/dusk after _TEST_DATETIME at the default test location (San Diego),
# precomputed to serve as an independent oracle for the trigger's scheduler.
_DAWN_DUSK = {
    ("dawn", "civil"): datetime(2015, 9, 15, 13, 7, 26, 84892, tzinfo=dt_util.UTC),
    ("dawn", "nautical"): datetime(2015, 9, 15, 12, 38, 34, 55317, tzinfo=dt_util.UTC),
    ("dawn", "astronomical"): datetime(
        2015, 9, 15, 12, 9, 9, 742065, tzinfo=dt_util.UTC
    ),
    ("dusk", "civil"): datetime(2015, 9, 15, 2, 21, 39, 56429, tzinfo=dt_util.UTC),
    ("dusk", "nautical"): datetime(2015, 9, 15, 2, 50, 29, 596023, tzinfo=dt_util.UTC),
    ("dusk", "astronomical"): datetime(
        2015, 9, 15, 3, 19, 52, 663966, tzinfo=dt_util.UTC
    ),
}


@pytest.fixture(autouse=True)
async def setup_comp(hass: HomeAssistant) -> None:
    """Initialize components."""
    mock_component(hass, "group")
    await async_setup_component(hass, sun.DOMAIN, {sun.DOMAIN: {}})


async def _arm_automation(
    hass: HomeAssistant, trigger: dict[str, Any], extra_data: dict[str, Any]
) -> None:
    """Set up an automation with the given trigger config."""
    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": trigger,
                "action": {
                    "service": "test.automation",
                    "data_template": extra_data,
                },
            }
        },
    )


# --- Legacy ``platform: sun`` backwards compatibility ------------------------


async def test_sunset_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the legacy sunset trigger."""
    now = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 2, tzinfo=dt_util.UTC)

    with freeze_time(now):
        await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {"platform": "sun", "event": SUN_EVENT_SUNSET},
                    "action": {
                        "service": "test.automation",
                        "data_template": {"id": "{{ trigger.id}}"},
                    },
                }
            },
        )

        await hass.services.async_call(
            automation.DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
            blocking=True,
        )
        assert len(service_calls) == 1

        async_fire_time_changed(hass, trigger_time)
        await hass.async_block_till_done()
        assert len(service_calls) == 1

    with freeze_time(now):
        await hass.services.async_call(
            automation.DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
            blocking=True,
        )
        assert len(service_calls) == 2

        async_fire_time_changed(hass, trigger_time)
        await hass.async_block_till_done()
        assert len(service_calls) == 3
        assert service_calls[2].data["id"] == 0


async def test_sunrise_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the legacy sunrise trigger."""
    now = datetime(2015, 9, 13, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 14, tzinfo=dt_util.UTC)

    with freeze_time(now):
        await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {"platform": "sun", "event": SUN_EVENT_SUNRISE},
                    "action": {"service": "test.automation"},
                }
            },
        )

        async_fire_time_changed(hass, trigger_time)
        await hass.async_block_till_done()
        assert len(service_calls) == 1


async def test_sunset_trigger_with_offset(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the legacy sunset trigger with offset."""
    now = datetime(2015, 9, 15, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 2, 30, tzinfo=dt_util.UTC)

    with freeze_time(now):
        await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "sun",
                        "event": SUN_EVENT_SUNSET,
                        "offset": "0:30:00",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "{{ trigger.platform }}"
                                " - {{ trigger.event }}"
                                " - {{ trigger.offset }}"
                            )
                        },
                    },
                }
            },
        )

        async_fire_time_changed(hass, trigger_time)
        await hass.async_block_till_done()
        assert len(service_calls) == 1
        assert service_calls[0].data["some"] == "sun - sunset - 0:30:00"


async def test_sunrise_trigger_with_offset(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the legacy sunrise trigger with offset."""
    now = datetime(2015, 9, 13, 23, tzinfo=dt_util.UTC)
    trigger_time = datetime(2015, 9, 16, 13, 30, tzinfo=dt_util.UTC)

    with freeze_time(now):
        await async_setup_component(
            hass,
            automation.DOMAIN,
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "sun",
                        "event": SUN_EVENT_SUNRISE,
                        "offset": "-0:30:00",
                    },
                    "action": {"service": "test.automation"},
                }
            },
        )

        async_fire_time_changed(hass, trigger_time)
        await hass.async_block_till_done()
        assert len(service_calls) == 1


# --- Modern solar event triggers ---------------------------------------------


@pytest.mark.parametrize(
    ("trigger_key", "astral_event"),
    [
        ("sun.sunrise", SUN_EVENT_SUNRISE),
        ("sun.sunset", SUN_EVENT_SUNSET),
        ("sun.solar_noon", "noon"),
        ("sun.solar_midnight", "midnight"),
    ],
)
async def test_event_trigger_fires(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger_key: str,
    astral_event: str,
) -> None:
    """Test the modern solar event triggers fire at the event time."""
    with freeze_time(_TEST_DATETIME):
        await _arm_automation(hass, {"platform": trigger_key}, {})
        expected = get_astral_event_next(hass, astral_event, _TEST_DATETIME)

        async_fire_time_changed(hass, expected + timedelta(seconds=1))
        await hass.async_block_till_done()

    assert len(service_calls) == 1


async def test_event_trigger_reschedules(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test that a solar event trigger reschedules for the following day."""
    with freeze_time(_TEST_DATETIME) as freezer:
        await _arm_automation(hass, {"platform": "sun.sunrise"}, {})
        first = get_astral_event_next(hass, SUN_EVENT_SUNRISE, _TEST_DATETIME)

        freezer.move_to(first + timedelta(seconds=1))
        async_fire_time_changed(hass, first + timedelta(seconds=1))
        await hass.async_block_till_done()
        assert len(service_calls) == 1

        # The reschedule computes the next event from the now-advanced clock.
        second = get_astral_event_next(hass, SUN_EVENT_SUNRISE, first)
        assert second > first

        freezer.move_to(second + timedelta(seconds=1))
        async_fire_time_changed(hass, second + timedelta(seconds=1))
        await hass.async_block_till_done()
        assert len(service_calls) == 2


async def test_event_trigger_reschedules_on_location_change(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test a solar event trigger reschedules when the location changes."""
    with freeze_time(_TEST_DATETIME):
        await _arm_automation(hass, {"platform": "sun.sunrise"}, {})
        first = get_astral_event_next(hass, SUN_EVENT_SUNRISE, _TEST_DATETIME)

        # Move far east so the next sunrise occurs earlier (in UTC) than before.
        await hass.config.async_update(latitude=51.5, longitude=0.0)
        await hass.async_block_till_done()
        rescheduled = get_astral_event_next(hass, SUN_EVENT_SUNRISE, _TEST_DATETIME)
        assert rescheduled < first

        # Firing at the new, earlier event time proves the schedule moved with it:
        # the original schedule pointed at the later sunrise and would not fire yet.
        async_fire_time_changed(hass, rescheduled + timedelta(seconds=1))
        await hass.async_block_till_done()
        assert len(service_calls) == 1


@pytest.mark.parametrize("trigger_key", ["sun.dawn", "sun.dusk"])
@pytest.mark.parametrize("twilight", ["civil", "nautical", "astronomical"])
async def test_dawn_dusk_trigger_fires(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger_key: str,
    twilight: str,
) -> None:
    """Test the dawn and dusk triggers fire for each twilight phase."""
    event = trigger_key.split(".")[1]
    with freeze_time(_TEST_DATETIME):
        await _arm_automation(
            hass,
            {"platform": trigger_key, "options": {"type": twilight}},
            {"type": "{{ trigger.type }}"},
        )
        expected = _DAWN_DUSK[event, twilight]

        async_fire_time_changed(hass, expected + timedelta(seconds=1))
        await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["type"] == twilight


async def test_dawn_defaults_to_civil(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the dawn trigger defaults to civil twilight."""
    with freeze_time(_TEST_DATETIME):
        await _arm_automation(
            hass, {"platform": "sun.dawn"}, {"type": "{{ trigger.type }}"}
        )
        # Nautical dawn happens earlier than civil dawn and must not fire.
        civil = _DAWN_DUSK["dawn", "civil"]
        nautical = _DAWN_DUSK["dawn", "nautical"]
        assert nautical < civil

        async_fire_time_changed(hass, nautical + timedelta(seconds=1))
        await hass.async_block_till_done()
        assert len(service_calls) == 0

        async_fire_time_changed(hass, civil + timedelta(seconds=1))
        await hass.async_block_till_done()
        assert len(service_calls) == 1
        assert service_calls[0].data["type"] == "civil"


# --- Edge cases: no matching solar event on the following day ----------------

# Longyearbyen, Svalbard (deep polar latitude) and Kotzebue, Alaska (above the
# Arctic Circle and far west of its time-zone meridian, i.e. heavily skewed
# local time). Both have stretches of weeks without a given solar event.
_SVALBARD = (78.22, 15.65, "Europe/Oslo")
_KOTZEBUE = (66.8983, -162.5966, "America/Anchorage")

# A two-sunrise day is the mirror of Kotzebue's two-sunset day: it needs solar
# noon (not midnight) near local midnight, which no real location has because
# time zones keep solar noon near local noon. This synthetic location forces it
# with a polar latitude on a deliberately ~12 h-offset time zone.
_TWO_SUNRISE_LOCATION = (66.5, -32.5, "America/Anchorage")


@pytest.mark.parametrize(
    ("location", "now", "trigger_key", "astral_event", "options", "depression"),
    [
        # Polar night: no sunrise for ~2 months.
        (
            _SVALBARD,
            datetime(2015, 12, 15, 12, tzinfo=dt_util.UTC),
            "sun.sunrise",
            "sunrise",
            {},
            None,
        ),
        # Midnight sun (skewed time zone): no sunset for ~6 weeks.
        (
            _KOTZEBUE,
            datetime(2015, 6, 15, 12, tzinfo=dt_util.UTC),
            "sun.sunset",
            "sunset",
            {},
            None,
        ),
        # No civil dawn at Svalbard during polar night.
        (
            _SVALBARD,
            datetime(2015, 12, 15, 12, tzinfo=dt_util.UTC),
            "sun.dawn",
            "dawn",
            {"type": "civil"},
            6.0,
        ),
        # No civil dusk at Kotzebue around the summer solstice (skewed tz).
        (
            _KOTZEBUE,
            datetime(2015, 6, 15, 12, tzinfo=dt_util.UTC),
            "sun.dusk",
            "dusk",
            {"type": "civil"},
            6.0,
        ),
    ],
)
async def test_event_trigger_no_event_next_day(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    location: tuple[float, float, str],
    now: datetime,
    trigger_key: str,
    astral_event: str,
    options: dict[str, Any],
    depression: float | None,
) -> None:
    """Test event triggers scan forward to the next day that has the event."""
    latitude, longitude, time_zone = location
    await hass.config.async_set_time_zone(time_zone)
    await hass.config.async_update(latitude=latitude, longitude=longitude, elevation=0)

    with freeze_time(now):
        await _arm_automation(hass, {"platform": trigger_key, "options": options}, {})
        expected = get_observer_astral_event_next(
            get_astral_observer(hass), astral_event, now, depression=depression
        )
        # The event does not occur on the following day at this latitude/season.
        assert expected > now + timedelta(days=1)

        async_fire_time_changed(hass, expected + timedelta(seconds=1))
        await hass.async_block_till_done()

    assert len(service_calls) == 1


async def test_two_sunsets_on_one_day_at_kotzebue(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test both sunsets fire on a calendar day that has two.

    Kotzebue's far-west longitude on Alaska time puts solar midnight near local
    midnight in early August, so 2015-08-07 (local) has two sunsets ~24 h apart
    - one just after midnight and one just before - and the scheduler must fire
    for both rather than skipping the second.
    """
    latitude, longitude, time_zone = _KOTZEBUE
    await hass.config.async_set_time_zone(time_zone)
    await hass.config.async_update(latitude=latitude, longitude=longitude, elevation=0)

    # 2015-08-07 08:03:42 UTC (00:03 local) and 2015-08-08 07:59:25 UTC (23:59 local)
    now = datetime(2015, 8, 7, 7, tzinfo=dt_util.UTC)
    with freeze_time(now) as freezer:
        await _arm_automation(hass, {"platform": "sun.sunset"}, {})
        first = get_astral_event_next(hass, "sunset", now)
        second = get_astral_event_next(hass, "sunset", first)
        # Two sunsets ~24 h apart that share one local calendar day.
        assert dt_util.as_local(first).date() == dt_util.as_local(second).date()
        assert timedelta(hours=23) < second - first < timedelta(hours=25)

        freezer.move_to(first + timedelta(seconds=1))
        async_fire_time_changed(hass, first + timedelta(seconds=1))
        await hass.async_block_till_done()
        assert len(service_calls) == 1

        freezer.move_to(second + timedelta(seconds=1))
        async_fire_time_changed(hass, second + timedelta(seconds=1))
        await hass.async_block_till_done()
        assert len(service_calls) == 2


async def test_two_sunrises_on_one_day(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test both sunrises fire on a calendar day that has two.

    The mirror of the two-sunset case: a synthetic polar location on a
    deliberately offset time zone puts solar noon near local midnight, so
    2015-03-07 (local) has two sunrises ~24 h apart - one just after midnight
    and one just before - and the scheduler must fire for both.
    """
    latitude, longitude, time_zone = _TWO_SUNRISE_LOCATION
    await hass.config.async_set_time_zone(time_zone)
    await hass.config.async_update(latitude=latitude, longitude=longitude, elevation=0)

    # 2015-03-07 09:02:36 UTC (00:02 local) and 2015-03-08 08:58:43 UTC (23:58 local)
    now = datetime(2015, 3, 7, 9, tzinfo=dt_util.UTC)
    with freeze_time(now) as freezer:
        await _arm_automation(hass, {"platform": "sun.sunrise"}, {})
        first = get_astral_event_next(hass, "sunrise", now)
        second = get_astral_event_next(hass, "sunrise", first)
        # Two sunrises ~24 h apart that share one local calendar day.
        assert dt_util.as_local(first).date() == dt_util.as_local(second).date()
        assert timedelta(hours=23) < second - first < timedelta(hours=25)

        freezer.move_to(first + timedelta(seconds=1))
        async_fire_time_changed(hass, first + timedelta(seconds=1))
        await hass.async_block_till_done()
        assert len(service_calls) == 1

        freezer.move_to(second + timedelta(seconds=1))
        async_fire_time_changed(hass, second + timedelta(seconds=1))
        await hass.async_block_till_done()
        assert len(service_calls) == 2


@pytest.mark.parametrize(
    ("trigger_key", "astral_event", "now", "above_horizon"),
    [
        # Midnight sun at Svalbard: solar midnight still occurs, with the sun's
        # lowest point above the horizon.
        (
            "sun.solar_midnight",
            "midnight",
            datetime(2015, 6, 15, tzinfo=dt_util.UTC),
            True,
        ),
        # Polar night at Svalbard: solar noon still occurs, with the sun's
        # highest point below the horizon.
        (
            "sun.solar_noon",
            "noon",
            datetime(2015, 12, 15, tzinfo=dt_util.UTC),
            False,
        ),
    ],
)
async def test_solar_noon_midnight_in_polar_regions(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    trigger_key: str,
    astral_event: str,
    now: datetime,
    above_horizon: bool,
) -> None:
    """Test solar noon/midnight fire even when the sun never crosses the horizon.

    Solar noon and solar midnight are the extremes of the sun's daily arc, so
    they occur every day regardless of the horizon: solar midnight happens during
    midnight sun (sun stays up) and solar noon happens during polar night (sun
    stays down).
    """
    latitude, longitude, time_zone = _SVALBARD
    await hass.config.async_set_time_zone(time_zone)
    await hass.config.async_update(latitude=latitude, longitude=longitude, elevation=0)

    with freeze_time(now):
        await _arm_automation(hass, {"platform": trigger_key}, {})
        expected = get_astral_event_next(hass, astral_event, now)
        # The defining property: at the sun's lowest point it is still up
        # (midnight sun), or at its highest point it is still down (polar night).
        elevation = astral_elevation(get_astral_observer(hass), expected)
        assert (elevation > -0.833) is above_horizon

        async_fire_time_changed(hass, expected + timedelta(seconds=1))
        await hass.async_block_till_done()

    assert len(service_calls) == 1


# --- Sun elevation triggers --------------------------------------------------


async def test_elevation_changed_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the elevation changed trigger fires on any elevation change."""
    await _arm_automation(
        hass,
        {
            "platform": "sun.elevation_changed",
            "options": {"threshold": {"type": "any"}},
        },
        {},
    )

    hass.states.async_set(_SUN_ENTITY_ID, "above_horizon", {"elevation": 5.0})
    await hass.async_block_till_done()
    calls_before = len(service_calls)

    hass.states.async_set(_SUN_ENTITY_ID, "above_horizon", {"elevation": 6.0})
    await hass.async_block_till_done()
    assert len(service_calls) == calls_before + 1


async def test_elevation_crossed_threshold_trigger(
    hass: HomeAssistant, service_calls: list[ServiceCall]
) -> None:
    """Test the elevation crossed threshold trigger fires only on crossing."""
    await _arm_automation(
        hass,
        {
            "platform": "sun.elevation_crossed_threshold",
            "options": {"threshold": {"type": "above", "value": {"number": 10}}},
        },
        {},
    )

    hass.states.async_set(_SUN_ENTITY_ID, "above_horizon", {"elevation": 5.0})
    await hass.async_block_till_done()
    calls_before = len(service_calls)

    # Crossing from below to above the threshold fires once.
    hass.states.async_set(_SUN_ENTITY_ID, "above_horizon", {"elevation": 15.0})
    await hass.async_block_till_done()
    assert len(service_calls) == calls_before + 1

    # Staying above the threshold does not fire again.
    hass.states.async_set(_SUN_ENTITY_ID, "above_horizon", {"elevation": 20.0})
    await hass.async_block_till_done()
    assert len(service_calls) == calls_before + 1


# --- Validation --------------------------------------------------------------


@pytest.mark.parametrize(
    "trigger_key",
    [
        "sun.sunrise",
        "sun.sunset",
        "sun.solar_noon",
        "sun.solar_midnight",
        "sun.dawn",
        "sun.dusk",
    ],
)
async def test_event_trigger_options(hass: HomeAssistant, trigger_key: str) -> None:
    """Test the solar event triggers reject behavior and duration options."""
    await assert_trigger_options_supported(
        hass,
        trigger_key,
        None,
        supports_behavior=False,
        supports_duration=False,
        supports_target=False,
    )


@pytest.mark.parametrize(
    ("trigger_key", "base_options", "supports_duration"),
    [
        ("sun.elevation_changed", {"threshold": {"type": "any"}}, False),
        (
            "sun.elevation_crossed_threshold",
            {"threshold": {"type": "above", "value": {"number": 10}}},
            True,
        ),
    ],
)
async def test_elevation_trigger_options(
    hass: HomeAssistant,
    trigger_key: str,
    base_options: dict[str, Any],
    supports_duration: bool,
) -> None:
    """Test the elevation triggers support the expected options without a target."""
    await assert_trigger_options_supported(
        hass,
        trigger_key,
        base_options,
        supports_behavior=False,
        supports_duration=supports_duration,
        supports_target=False,
    )


@pytest.mark.parametrize(
    ("twilight", "valid"),
    [
        ("civil", True),
        ("nautical", True),
        ("astronomical", True),
        ("invalid", False),
    ],
)
async def test_dawn_dusk_twilight_validation(
    hass: HomeAssistant, twilight: str, valid: bool
) -> None:
    """Test the dawn/dusk triggers validate the twilight option."""
    config = {"platform": "sun.dawn", "options": {"type": twilight}}
    if valid:
        await async_validate_trigger_config(hass, [config])
    else:
        with pytest.raises(vol.Invalid):
            await async_validate_trigger_config(hass, [config])

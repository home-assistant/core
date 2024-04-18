"""The tests for time_date sensor platform."""

from unittest.mock import ANY, Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.time_date.const import DOMAIN, OPTION_TYPES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import event, issue_registry as ir
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from . import load_int

from tests.common import async_fire_time_changed


@patch("homeassistant.components.time_date.sensor.async_track_point_in_utc_time")
@pytest.mark.parametrize(
    ("display_option", "start_time", "tracked_time"),
    [
        (
            "time",
            dt_util.utc_from_timestamp(45.5),
            dt_util.utc_from_timestamp(60),
        ),
        (
            "beat",
            dt_util.parse_datetime("2020-11-13 00:00:29+01:00"),
            dt_util.parse_datetime("2020-11-13 00:01:26.4+01:00"),
        ),
        (
            "date_time",
            dt_util.utc_from_timestamp(1495068899),
            dt_util.utc_from_timestamp(1495068900),
        ),
        (
            "time_date",
            dt_util.utc_from_timestamp(1495068899),
            dt_util.utc_from_timestamp(1495068900),
        ),
    ],
)
async def test_intervals(
    mock_track_interval: Mock,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    display_option: str,
    start_time,
    tracked_time,
) -> None:
    """Test timing intervals of sensors when time zone is UTC."""
    hass.config.set_time_zone("UTC")
    freezer.move_to(start_time)

    await load_int(hass, display_option)

    mock_track_interval.assert_called_once_with(hass, ANY, tracked_time)


async def test_states(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Test states of sensors."""
    hass.config.set_time_zone("UTC")
    now = dt_util.utc_from_timestamp(1495068856)
    freezer.move_to(now)

    for option in OPTION_TYPES:
        await load_int(hass, option)

    state = hass.states.get("sensor.time")
    assert state.state == "00:54"

    state = hass.states.get("sensor.date")
    assert state.state == "2017-05-18"

    state = hass.states.get("sensor.time_utc")
    assert state.state == "00:54"

    state = hass.states.get("sensor.date_time")
    assert state.state == "2017-05-18, 00:54"

    state = hass.states.get("sensor.date_time_utc")
    assert state.state == "2017-05-18, 00:54"

    state = hass.states.get("sensor.internet_time")
    assert state.state == "@079"

    state = hass.states.get("sensor.date_time_iso")
    assert state.state == "2017-05-18T00:54:00"

    # Time travel
    now = dt_util.utc_from_timestamp(1602952963.2)
    freezer.move_to(now)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.time")
    assert state.state == "16:42"

    state = hass.states.get("sensor.date")
    assert state.state == "2020-10-17"

    state = hass.states.get("sensor.time_utc")
    assert state.state == "16:42"

    state = hass.states.get("sensor.date_time")
    assert state.state == "2020-10-17, 16:42"

    state = hass.states.get("sensor.date_time_utc")
    assert state.state == "2020-10-17, 16:42"

    state = hass.states.get("sensor.internet_time")
    assert state.state == "@738"

    state = hass.states.get("sensor.date_time_iso")
    assert state.state == "2020-10-17T16:42:00"


async def test_states_non_default_timezone(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test states of sensors in a timezone other than UTC."""
    hass.config.set_time_zone("America/New_York")
    now = dt_util.utc_from_timestamp(1495068856)
    freezer.move_to(now)

    for option in OPTION_TYPES:
        await load_int(hass, option)

    state = hass.states.get("sensor.time")
    assert state.state == "20:54"

    state = hass.states.get("sensor.date")
    assert state.state == "2017-05-17"

    state = hass.states.get("sensor.time_utc")
    assert state.state == "00:54"

    state = hass.states.get("sensor.date_time")
    assert state.state == "2017-05-17, 20:54"

    state = hass.states.get("sensor.date_time_utc")
    assert state.state == "2017-05-18, 00:54"

    state = hass.states.get("sensor.internet_time")
    assert state.state == "@079"

    state = hass.states.get("sensor.date_time_iso")
    assert state.state == "2017-05-17T20:54:00"

    # Time travel
    now = dt_util.utc_from_timestamp(1602952963.2)
    freezer.move_to(now)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.time")
    assert state.state == "12:42"

    state = hass.states.get("sensor.date")
    assert state.state == "2020-10-17"

    state = hass.states.get("sensor.time_utc")
    assert state.state == "16:42"

    state = hass.states.get("sensor.date_time")
    assert state.state == "2020-10-17, 12:42"

    state = hass.states.get("sensor.date_time_utc")
    assert state.state == "2020-10-17, 16:42"

    state = hass.states.get("sensor.internet_time")
    assert state.state == "@738"

    state = hass.states.get("sensor.date_time_iso")
    assert state.state == "2020-10-17T12:42:00"

    # Change time zone
    await hass.config.async_update(time_zone="Europe/Prague")
    await hass.async_block_till_done()

    state = hass.states.get("sensor.time")
    assert state.state == "18:42"

    state = hass.states.get("sensor.date")
    assert state.state == "2020-10-17"

    state = hass.states.get("sensor.time_utc")
    assert state.state == "16:42"

    state = hass.states.get("sensor.date_time")
    assert state.state == "2020-10-17, 18:42"

    state = hass.states.get("sensor.date_time_utc")
    assert state.state == "2020-10-17, 16:42"

    state = hass.states.get("sensor.internet_time")
    assert state.state == "@738"

    state = hass.states.get("sensor.date_time_iso")
    assert state.state == "2020-10-17T18:42:00"


@patch(
    "homeassistant.components.time_date.sensor.async_track_point_in_utc_time",
    side_effect=event.async_track_point_in_utc_time,
)
@pytest.mark.parametrize(
    ("time_zone", "start_time", "tracked_time"),
    [
        (
            "America/New_York",
            dt_util.utc_from_timestamp(50000),
            # start of local day in EST was 18000.0
            # so the second day was 18000 + 86400
            104400,
        ),
        (
            "America/Edmonton",
            dt_util.parse_datetime("2017-11-13 19:47:19-07:00"),
            dt_util.as_timestamp("2017-11-14 00:00:00-07:00"),
        ),
        # Entering DST
        (
            "Europe/Prague",
            dt_util.parse_datetime("2020-03-29 00:00+01:00"),
            dt_util.as_timestamp("2020-03-30 00:00+02:00"),
        ),
        (
            "Europe/Prague",
            dt_util.parse_datetime("2020-03-29 03:00+02:00"),
            dt_util.as_timestamp("2020-03-30 00:00+02:00"),
        ),
        # Leaving DST
        (
            "Europe/Prague",
            dt_util.parse_datetime("2020-10-25 00:00+02:00"),
            dt_util.as_timestamp("2020-10-26 00:00+01:00"),
        ),
        (
            "Europe/Prague",
            dt_util.parse_datetime("2020-10-25 23:59+01:00"),
            dt_util.as_timestamp("2020-10-26 00:00+01:00"),
        ),
    ],
)
async def test_timezone_intervals(
    mock_track_interval: Mock,
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    time_zone: str,
    start_time,
    tracked_time,
) -> None:
    """Test timing intervals of sensors in timezone other than UTC."""
    hass.config.set_time_zone(time_zone)
    freezer.move_to(start_time)

    await load_int(hass, "date")

    mock_track_interval.assert_called_once()
    next_time = mock_track_interval.mock_calls[0][1][2]

    assert next_time.timestamp() == tracked_time


async def test_icons(hass: HomeAssistant) -> None:
    """Test attributes of sensors."""
    for option in OPTION_TYPES:
        await load_int(hass, option)

    state = hass.states.get("sensor.time")
    assert state.attributes["icon"] == "mdi:clock"
    state = hass.states.get("sensor.date")
    assert state.attributes["icon"] == "mdi:calendar"
    state = hass.states.get("sensor.time_utc")
    assert state.attributes["icon"] == "mdi:clock"
    state = hass.states.get("sensor.date_time")
    assert state.attributes["icon"] == "mdi:calendar-clock"
    state = hass.states.get("sensor.date_time_utc")
    assert state.attributes["icon"] == "mdi:calendar-clock"
    state = hass.states.get("sensor.internet_time")
    assert state.attributes["icon"] == "mdi:clock"
    state = hass.states.get("sensor.date_time_iso")
    assert state.attributes["icon"] == "mdi:calendar-clock"


@pytest.mark.parametrize(
    (
        "display_options",
        "expected_warnings",
        "expected_issues",
    ),
    [
        (["time", "date"], [], []),
        (["beat"], ["'beat': is deprecated"], ["deprecated_beat"]),
        (["time", "beat"], ["'beat': is deprecated"], ["deprecated_beat"]),
    ],
)
async def test_deprecation_warning(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    display_options: list[str],
    expected_warnings: list[str],
    expected_issues: list[str],
) -> None:
    """Test deprecation warning for swatch beat."""
    config = {
        "sensor": {
            "platform": "time_date",
            "display_options": display_options,
        }
    }

    assert await async_setup_component(hass, "sensor", config)
    await hass.async_block_till_done()

    warnings = [record for record in caplog.records if record.levelname == "WARNING"]
    assert len(warnings) == len(expected_warnings)
    for expected_warning in expected_warnings:
        assert any(expected_warning in warning.message for warning in warnings)

    issue_registry = ir.async_get(hass)
    assert len(issue_registry.issues) == len(expected_issues)
    for expected_issue in expected_issues:
        assert (DOMAIN, expected_issue) in issue_registry.issues

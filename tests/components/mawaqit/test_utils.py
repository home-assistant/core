"""Tests for the Mawaqit utility functions."""

from datetime import date, datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from freezegun import freeze_time
import pytest

from homeassistant.components.mawaqit import utils
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_UUID

# Shared calendar helpers from conftest — avoids re-defining month_data inline.
from .conftest import (
    IQAMA_ABSOLUTE_TIMES_ROW,
    IQAMA_OFFSET_TIMES_ROW,
    PRAYER_TIMES_ROW,
    make_iqama_month_data,
    make_month_data,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _calendar_with_april(extra_days: dict | None = None) -> list[dict]:
    """Return a 12-month calendar that only has April (index 3) filled.

    Args:
        extra_days: Optional extra day entries merged into the April dict
                    (e.g. ``{"11": [...]}`` to add the following day).

    """
    month = make_month_data()
    if extra_days:
        month.update(extra_days)
    calendar = [{} for _ in range(12)]
    calendar[3] = month
    return calendar


def _two_day_april_calendar() -> list[dict]:
    """April calendar with day 10 AND day 11 filled (for next-day look-ahead)."""
    return _calendar_with_april(
        extra_days={"11": ["05:29", "06:44", "12:29", "15:44", "18:29", "19:59"]}
    )


# ---------------------------------------------------------------------------
# _to_utc
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("time_str", ["", None])
def test_to_utc_falsy_time_string_returns_none(time_str) -> None:
    """Test _to_utc returns None for empty / None inputs."""
    assert utils._to_utc("Europe/Paris", date(2025, 4, 10), time_str) is None


# ---------------------------------------------------------------------------
# compute_islamic_midnight
# ---------------------------------------------------------------------------


def test_compute_islamic_midnight_isha_localization_fails() -> None:
    """Test compute_islamic_midnight returns None when isha localization fails."""
    prayer_data = {"calendar": _two_day_april_calendar()}
    target_date = date(2025, 4, 10)

    with patch(
        "homeassistant.components.mawaqit.utils.time_with_timezone",
        side_effect=[
            None,  # isha -> fails
            datetime(2025, 4, 11, 5, 29, tzinfo=ZoneInfo("Europe/Paris")),
        ],
    ):
        assert (
            utils.compute_islamic_midnight(prayer_data, target_date, "Europe/Paris")
            is None
        )


def test_compute_islamic_midnight_fajr_localization_fails() -> None:
    """Test compute_islamic_midnight returns None when fajr localization fails."""
    prayer_data = {"calendar": _two_day_april_calendar()}
    target_date = date(2025, 4, 10)

    with patch(
        "homeassistant.components.mawaqit.utils.time_with_timezone",
        side_effect=[
            datetime(2025, 4, 10, 20, 0, tzinfo=ZoneInfo("Europe/Paris")),  # isha ok
            None,  # fajr -> fails
        ],
    ):
        assert (
            utils.compute_islamic_midnight(prayer_data, target_date, "Europe/Paris")
            is None
        )


# ---------------------------------------------------------------------------
# save_mosque
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("kwargs", "expected_data"),
    [
        (
            {"lat": 48.0, "longi": 2.0},
            {
                CONF_API_KEY: "token",
                CONF_UUID: "uuid1",
                CONF_LATITUDE: 48.0,
                CONF_LONGITUDE: 2.0,
            },
        ),
        (
            {},
            {CONF_API_KEY: "token", CONF_UUID: "uuid1"},
        ),
    ],
)
def test_save_mosque(kwargs: dict, expected_data: dict) -> None:
    """Test saving mosque data with and without coordinates."""
    title, data = utils.save_mosque(
        mosque_display_name="My Mosque",
        mosque_id="uuid1",
        mawaqit_token="token",
        **kwargs,
    )
    assert title == "MAWAQIT - My Mosque"
    assert data == expected_data


def test_save_mosque_no_token() -> None:
    """Test saving mosque data with no token raises ValueError."""
    with pytest.raises(ValueError):
        utils.save_mosque(
            mosque_display_name="My Mosque",
            mosque_id="uuid1",
            mawaqit_token=None,
        )


# ---------------------------------------------------------------------------
# extract_time_from_calendar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("month_data", "mode_iqama", "expected"),
    [
        (make_month_data(), False, PRAYER_TIMES_ROW[0]),
        (make_iqama_month_data(), True, IQAMA_OFFSET_TIMES_ROW[0]),
    ],
)
def test_extract_time_from_calendar_success(month_data, mode_iqama, expected) -> None:
    """Test successful time extraction for standard and iqama modes."""
    calendar = [{} for _ in range(12)]
    calendar[3] = month_data  # April (index 3)
    result = utils.extract_time_from_calendar(
        calendar, "Fajr", date(2025, 4, 10), mode_iqama=mode_iqama
    )
    assert result == expected


@pytest.mark.parametrize(
    ("calendar", "prayer_name", "target_date", "mode_iqama"),
    [
        (
            [{"1": list(PRAYER_TIMES_ROW)}],
            "InvalidPrayer",
            date(2025, 1, 1),
            False,
        ),
        ([], "Fajr", date(2025, 1, 1), False),
        ([{}], "Fajr", date(2025, 1, 1), False),
        ([{"1": ["05:30"]}], "Fajr", date(2025, 1, 1), False),
    ],
)
def test_extract_time_from_calendar_returns_none(
    calendar, prayer_name, target_date, mode_iqama
) -> None:
    """Test extraction returns None for invalid / missing / incomplete data."""
    assert (
        utils.extract_time_from_calendar(
            calendar, prayer_name, target_date, mode_iqama=mode_iqama
        )
        is None
    )


# ---------------------------------------------------------------------------
# time_with_timezone
# ---------------------------------------------------------------------------


def test_time_with_timezone_valid() -> None:
    """Test converting time with valid timezone."""
    result = utils.time_with_timezone("Europe/Paris", "2025-04-10", "12:30")
    assert result is not None
    assert isinstance(result, datetime)


def test_time_with_timezone_invalid() -> None:
    """Test converting time with invalid timezone."""
    assert utils.time_with_timezone("Invalid/Timezone", "2025-04-10", "12:30") is None


# ---------------------------------------------------------------------------
# add_minutes_to_time
# ---------------------------------------------------------------------------


def test_add_minutes_to_time_valid() -> None:
    """Test adding minutes to time."""
    assert utils.add_minutes_to_time("12:30", "+15") == "12:45"


@pytest.mark.parametrize(
    ("time_str", "minutes_str", "match"),
    [
        (None, "+15", "Both time_str and minutes_str must be"),
        ("12:30", None, "Both time_str and minutes_str must be"),
        ("12:30", "15", "Invalid minutes format"),
        ("12:30", "+abc", "Invalid minutes format"),
    ],
)
def test_add_minutes_to_time_errors(time_str, minutes_str, match) -> None:
    """Test error cases for add_minutes_to_time."""
    with pytest.raises(ValueError, match=match):
        utils.add_minutes_to_time(time_str, minutes_str)


def test_add_minutes_to_time_internal_error() -> None:
    """Test add_minutes_to_time handles internal TypeError gracefully."""
    with patch(
        "homeassistant.components.mawaqit.utils.timedelta",
        side_effect=TypeError("mock error"),
    ):
        assert utils.add_minutes_to_time("12:30", "+15") is None


# ---------------------------------------------------------------------------
# get_next_friday
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("frozen_date", "expected_date"),
    [
        ("2025-04-07", date(2025, 4, 11)),  # Monday -> upcoming Friday
        ("2025-04-11", date(2025, 4, 18)),  # Friday -> next week's Friday
        ("2025-04-12", date(2025, 4, 18)),  # Saturday -> upcoming Friday
    ],
)
def test_get_next_friday(frozen_date: str, expected_date: date) -> None:
    """Test getting next Friday from various weekdays."""
    with freeze_time(frozen_date):
        assert utils.get_next_friday() == expected_date


# ---------------------------------------------------------------------------
# get_prayer_times_for_two_days
# ---------------------------------------------------------------------------


def test_get_prayer_times_for_two_days() -> None:
    """Test getting prayer times for today and tomorrow."""
    tz = ZoneInfo("Europe/Paris")
    today = datetime(2025, 4, 10, 12, 0, tzinfo=tz)

    result = utils.get_prayer_times_for_two_days(
        _two_day_april_calendar(), today, "Europe/Paris"
    )

    assert result["today"]["date"] == "2025-04-10"
    assert result["today"]["prayer_times"] == list(PRAYER_TIMES_ROW)
    assert result["tomorrow"]["date"] == "2025-04-11"


# ---------------------------------------------------------------------------
# find_next_prayer
# ---------------------------------------------------------------------------


def test_find_next_prayer_today() -> None:
    """Test finding next prayer when there is one remaining today."""
    tz = ZoneInfo("Europe/Paris")
    current_time = datetime(2025, 4, 10, 14, 0, tzinfo=tz)

    index, prayer_time = utils.find_next_prayer(
        current_time, _two_day_april_calendar(), "Europe/Paris"
    )
    assert index == 3  # Asr at 15:45 is next after 14:00
    assert prayer_time is not None


def test_find_next_prayer_tomorrow() -> None:
    """Test finding next prayer when all today's prayers have passed."""
    tz = ZoneInfo("Europe/Paris")
    current_time = datetime(2025, 4, 10, 23, 0, tzinfo=tz)

    index, prayer_time = utils.find_next_prayer(
        current_time, _two_day_april_calendar(), "Europe/Paris"
    )
    assert index == 0  # First prayer tomorrow
    assert prayer_time is not None


def test_find_next_prayer_invalid_timezone() -> None:
    """Test finding next prayer with an invalid timezone."""
    tz = ZoneInfo("Europe/Paris")
    current_time = datetime(2025, 4, 10, 12, 0, tzinfo=tz)

    index, prayer_time = utils.find_next_prayer(current_time, [{}], "Invalid/Timezone")
    assert index is None
    assert prayer_time is None


# ---------------------------------------------------------------------------
# get_regular_prayer_time
# ---------------------------------------------------------------------------


@freeze_time("2025-04-10 12:00:00+02:00")
@pytest.mark.parametrize(
    ("prayer_data", "expect_datetime"),
    [
        (
            {
                "calendar": [make_month_data() for _ in range(12)],
                "timezone": "Europe/Paris",
            },
            True,
        ),
        ({}, False),
        ({"calendar": [{}], "timezone": "Europe/Paris"}, False),
    ],
)
def test_get_regular_prayer_time(prayer_data, expect_datetime) -> None:
    """Test get_regular_prayer_time with valid and missing data."""
    result = utils.get_regular_prayer_time(prayer_data, "Fajr")
    if expect_datetime:
        assert isinstance(result, datetime)
    else:
        assert result is None


@freeze_time("2025-04-10 12:00:00+02:00")
def test_get_regular_prayer_time_invalid_timezone() -> None:
    """Test get_regular_prayer_time when time_with_timezone returns None."""
    prayer_data = {"calendar": _calendar_with_april(), "timezone": "Europe/Paris"}
    with patch(
        "homeassistant.components.mawaqit.utils.time_with_timezone",
        return_value=None,
    ):
        assert utils.get_regular_prayer_time(prayer_data, "Fajr") is None


# ---------------------------------------------------------------------------
# get_shuruq_time
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("prayer_data", "expected_none"),
    [
        ({"timezone": "Europe/Paris", "shuruq": "06:45"}, False),
        ({"shuruq": "06:45"}, True),
        ({"timezone": "Europe/Paris"}, True),
    ],
)
@freeze_time("2025-04-10 12:00:00+02:00")
def test_get_shuruq_time(prayer_data, expected_none) -> None:
    """Test get_shuruq_time with valid data and missing fields."""
    result = utils.get_shuruq_time(prayer_data)
    if expected_none:
        assert result is None
    else:
        assert isinstance(result, datetime)


@freeze_time("2025-04-10 12:00:00+02:00")
def test_get_shuruq_time_invalid_localization() -> None:
    """Test get_shuruq_time when localization fails."""
    prayer_data = {"timezone": "Europe/Paris", "shuruq": "06:45"}
    with patch(
        "homeassistant.components.mawaqit.utils.time_with_timezone",
        return_value=None,
    ):
        assert utils.get_shuruq_time(prayer_data) is None


# ---------------------------------------------------------------------------
# get_jumua_time
# ---------------------------------------------------------------------------


def test_get_jumua_time_success() -> None:
    """Test getting jumua time successfully."""
    result = utils.get_jumua_time(
        {"timezone": "Europe/Paris", "jumua": "13:00"}, "jumua"
    )
    assert isinstance(result, datetime)


def test_get_jumua_time_no_timezone() -> None:
    """Test getting jumua time without timezone returns None."""
    assert utils.get_jumua_time({"jumua": "13:00"}, "jumua") is None


def test_get_jumua_time_no_jumua() -> None:
    """Test getting jumua time when jumua key is absent returns None."""
    assert utils.get_jumua_time({"timezone": "Europe/Paris"}, "jumua") is None


def test_get_jumua_time_invalid_localization() -> None:
    """Test getting jumua time when localization fails."""
    with patch(
        "homeassistant.components.mawaqit.utils.time_with_timezone",
        return_value=None,
    ):
        assert (
            utils.get_jumua_time(
                {"timezone": "Europe/Paris", "jumua": "13:00"}, "jumua"
            )
            is None
        )


# ---------------------------------------------------------------------------
# parse_iqama_time
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("prayer_time", "iqama_time", "expected"),
    [
        ("05:30", "+10", "05:40"),  # offset
        ("05:30", "+0", "05:30"),  # zero offset
        ("05:30", "06:15", "06:15"),  # absolute
        ("20:00", "06:15", "06:15"),  # absolute ignores prayer_time
    ],
)
def test_parse_iqama_time_valid(prayer_time, iqama_time, expected) -> None:
    """Test parse_iqama_time with valid formats."""
    assert utils.parse_iqama_time(prayer_time, iqama_time) == expected


@pytest.mark.parametrize(
    "iqama_time",
    ["", "invalid", "5:30", "05:3"],
)
def test_parse_iqama_time_returns_none(iqama_time) -> None:
    """Test parse_iqama_time with invalid / empty formats returns None."""
    assert utils.parse_iqama_time("05:30", iqama_time) is None


# ---------------------------------------------------------------------------
# get_iqama_time
# ---------------------------------------------------------------------------


@freeze_time("2025-04-10 12:00:00+02:00")
@pytest.mark.parametrize(
    ("iqama_day_data", "expected_hour", "expected_minute"),
    [
        (
            list(IQAMA_ABSOLUTE_TIMES_ROW),
            3,
            45,
        ),  # absolute: 05:45 Paris = 03:45 UTC
        (
            list(IQAMA_OFFSET_TIMES_ROW),
            3,
            40,
        ),  # offset: 05:30+10m Paris = 03:40 UTC
    ],
)
def test_get_iqama_time_formats(iqama_day_data, expected_hour, expected_minute) -> None:
    """Test get_iqama_time with absolute and offset iqama formats."""
    calendar = _calendar_with_april()
    iqama_calendar = [{} for _ in range(12)]
    iqama_calendar[3] = {"10": iqama_day_data}

    prayer_data = {
        "calendar": calendar,
        "iqamaCalendar": iqama_calendar,
        "timezone": "Europe/Paris",
    }
    result = utils.get_iqama_time(prayer_data, "Fajr")
    assert isinstance(result, datetime)
    assert result.hour == expected_hour
    assert result.minute == expected_minute


@freeze_time("2025-04-10 12:00:00+02:00")
@pytest.mark.parametrize(
    "prayer_data",
    [
        {},
        {"calendar": [{}], "iqamaCalendar": [{}], "timezone": "Europe/Paris"},
        {
            "calendar": _calendar_with_april(),
            "iqamaCalendar": [{}],
            "timezone": "Europe/Paris",
        },
    ],
)
def test_get_iqama_time_returns_none(prayer_data) -> None:
    """Test get_iqama_time returns None when required data is absent."""
    assert utils.get_iqama_time(prayer_data, "Fajr") is None


@freeze_time("2025-04-10 12:00:00+02:00")
def test_get_iqama_time_parse_returns_none() -> None:
    """Test get_iqama_time when parse_iqama_time returns None."""
    iqama_calendar = [{} for _ in range(12)]
    iqama_calendar[3] = make_iqama_month_data()
    prayer_data = {
        "calendar": _calendar_with_april(),
        "iqamaCalendar": iqama_calendar,
        "timezone": "Europe/Paris",
    }
    with patch(
        "homeassistant.components.mawaqit.utils.parse_iqama_time", return_value=None
    ):
        assert utils.get_iqama_time(prayer_data, "Fajr") is None


@freeze_time("2025-04-10 12:00:00+02:00")
def test_get_iqama_time_invalid_localization() -> None:
    """Test get_iqama_time when localization fails."""
    iqama_calendar = [{} for _ in range(12)]
    iqama_calendar[3] = make_iqama_month_data()
    prayer_data = {
        "calendar": _calendar_with_april(),
        "iqamaCalendar": iqama_calendar,
        "timezone": "Europe/Paris",
    }
    with patch(
        "homeassistant.components.mawaqit.utils.time_with_timezone", return_value=None
    ):
        assert utils.get_iqama_time(prayer_data, "Fajr") is None


# ---------------------------------------------------------------------------
# extract_time_from_calendar - error branches
# ---------------------------------------------------------------------------


def test_extract_time_key_error() -> None:
    """Test extract_time_from_calendar handles KeyError."""
    mock_month = MagicMock()
    mock_month.get = MagicMock(side_effect=KeyError("missing"))
    result = utils.extract_time_from_calendar([mock_month], "Fajr", date(2025, 1, 1))
    assert result is None


def test_extract_time_value_error() -> None:
    """Test extract_time_from_calendar handles ValueError from list.index()."""

    class FailIndexList(list):
        def index(self, value, *args):
            raise ValueError("not found")

    month_data = {"1": list(PRAYER_TIMES_ROW)}
    with patch(
        "homeassistant.components.mawaqit.utils.PRAYER_NAMES",
        new=FailIndexList(["fajr", "shuruq", "dhuhr", "asr", "maghrib", "isha"]),
    ):
        result = utils.extract_time_from_calendar(
            [month_data], "Fajr", date(2025, 1, 1)
        )
    assert result is None


def test_extract_time_index_error() -> None:
    """Test extract_time_from_calendar handles IndexError from list subscript."""

    class FailGetitemList(list):
        def __getitem__(self, index):
            raise IndexError("out of range")

    month_data = {"1": FailGetitemList(list(PRAYER_TIMES_ROW))}
    result = utils.extract_time_from_calendar([month_data], "Fajr", date(2025, 1, 1))
    assert result is None

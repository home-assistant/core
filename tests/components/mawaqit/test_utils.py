"""Tests for the Mawaqit utility functions."""

from datetime import date, datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from freezegun import freeze_time
import pytest

from homeassistant.components.mawaqit import utils
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_UUID

# --- _to_utc ---


@pytest.mark.parametrize("time_str", ["", None])
def test_to_utc_falsy_time_string_returns_none(time_str) -> None:
    """Test _to_utc returns None for odd inputs."""
    assert utils._to_utc("Europe/Paris", date(2025, 4, 10), time_str) is None


# --- compute_islamic_midnight ---


def test_compute_islamic_midnight_isha_localization_fails() -> None:
    """Test compute_islamic_midnight returns None when isha localization fails."""
    month_data = {
        "10": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"],
        "11": ["05:29", "06:44", "12:29", "15:44", "18:29", "19:59"],
    }
    calendar = [{} for _ in range(12)]
    calendar[3] = month_data

    prayer_data = {"calendar": calendar}
    target_date = date(2025, 4, 10)

    # First call (isha) returns None, second call (fajr) would be fine
    with patch(
        "homeassistant.components.mawaqit.utils.time_with_timezone",
        side_effect=[
            None,
            datetime(2025, 4, 11, 5, 29, tzinfo=ZoneInfo("Europe/Paris")),
        ],
    ):
        result = utils.compute_islamic_midnight(
            prayer_data, target_date, "Europe/Paris"
        )
        assert result is None


def test_compute_islamic_midnight_fajr_localization_fails() -> None:
    """Test compute_islamic_midnight returns None when fajr localization fails."""
    month_data = {
        "10": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"],
        "11": ["05:29", "06:44", "12:29", "15:44", "18:29", "19:59"],
    }
    calendar = [{} for _ in range(12)]
    calendar[3] = month_data

    prayer_data = {"calendar": calendar}
    target_date = date(2025, 4, 10)

    # First call (isha) succeeds, second call (fajr) returns None
    with patch(
        "homeassistant.components.mawaqit.utils.time_with_timezone",
        side_effect=[
            datetime(2025, 4, 10, 20, 0, tzinfo=ZoneInfo("Europe/Paris")),
            None,
        ],
    ):
        result = utils.compute_islamic_midnight(
            prayer_data, target_date, "Europe/Paris"
        )
        assert result is None


# --- save_mosque ---


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


# --- extract_time_from_calendar ---


@pytest.mark.parametrize(
    ("month_data", "mode_iqama", "expected"),
    [
        (
            {"10": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"]},
            False,
            "05:30",
        ),
        ({"10": ["+10", "+15", "+10", "+5", "+10"]}, True, "+10"),
    ],
)
def test_extract_time_from_calendar_success(month_data, mode_iqama, expected) -> None:
    """Test successful time extraction for standard and iqama modes."""
    calendar = [{} for _ in range(12)]
    calendar[3] = month_data  # April (index 3)
    target_date = date(2025, 4, 10)
    result = utils.extract_time_from_calendar(
        calendar, "Fajr", target_date, mode_iqama=mode_iqama
    )
    assert result == expected


@pytest.mark.parametrize(
    ("calendar", "prayer_name", "target_date", "mode_iqama"),
    [
        (
            [{"1": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"]}],
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
    """Test extraction returns None for invalid/missing/incomplete data."""
    assert (
        utils.extract_time_from_calendar(
            calendar, prayer_name, target_date, mode_iqama=mode_iqama
        )
        is None
    )


# --- time_with_timezone ---


def test_time_with_timezone_valid() -> None:
    """Test converting time with valid timezone."""
    result = utils.time_with_timezone("Europe/Paris", "2025-04-10", "12:30")
    assert result is not None
    assert isinstance(result, datetime)


def test_time_with_timezone_invalid() -> None:
    """Test converting time with invalid timezone."""
    result = utils.time_with_timezone("Invalid/Timezone", "2025-04-10", "12:30")
    assert result is None


# --- add_minutes_to_time ---


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


# --- get_next_friday ---


@pytest.mark.parametrize(
    ("frozen_date", "expected_date"),
    [
        ("2025-04-07", date(2025, 4, 11)),  # Monday
        ("2025-04-11", date(2025, 4, 18)),  # Friday → next week
        ("2025-04-12", date(2025, 4, 18)),  # Saturday
    ],
)
def test_get_next_friday(frozen_date: str, expected_date: date) -> None:
    """Test getting next Friday from various test cases."""
    with freeze_time(frozen_date):
        assert utils.get_next_friday() == expected_date


# --- get_prayer_times_for_two_days ---


def test_get_prayer_times_for_two_days() -> None:
    """Test getting prayer times for today and tomorrow."""
    month_data = {
        "10": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"],
        "11": ["05:29", "06:44", "12:29", "15:44", "18:29", "19:59"],
    }
    calendar = [{} for _ in range(12)]
    calendar[3] = month_data  # April

    tz = ZoneInfo("Europe/Paris")
    today = datetime(2025, 4, 10, 12, 0, tzinfo=tz)

    result = utils.get_prayer_times_for_two_days(calendar, today, "Europe/Paris")
    assert result["today"]["date"] == "2025-04-10"
    assert result["today"]["prayer_times"] == [
        "05:30",
        "06:45",
        "12:30",
        "15:45",
        "18:30",
        "20:00",
    ]
    assert result["tomorrow"]["date"] == "2025-04-11"


# --- find_next_prayer ---


def test_find_next_prayer_today() -> None:
    """Test finding next prayer when there's one remaining today."""
    month_data = {
        "10": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"],
        "11": ["05:29", "06:44", "12:29", "15:44", "18:29", "19:59"],
    }
    calendar = [{} for _ in range(12)]
    calendar[3] = month_data

    tz = ZoneInfo("Europe/Paris")
    current_time = datetime(2025, 4, 10, 14, 0, tzinfo=tz)

    index, prayer_time = utils.find_next_prayer(current_time, calendar, "Europe/Paris")
    assert index == 3  # Asr (15:45 is next after 14:00)
    assert prayer_time is not None


def test_find_next_prayer_tomorrow() -> None:
    """Test finding next prayer when all today's prayers have passed."""
    month_data = {
        "10": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"],
        "11": ["05:29", "06:44", "12:29", "15:44", "18:29", "19:59"],
    }
    calendar = [{} for _ in range(12)]
    calendar[3] = month_data

    tz = ZoneInfo("Europe/Paris")
    current_time = datetime(2025, 4, 10, 23, 0, tzinfo=tz)

    index, prayer_time = utils.find_next_prayer(current_time, calendar, "Europe/Paris")
    assert index == 0  # First prayer tomorrow
    assert prayer_time is not None


def test_find_next_prayer_invalid_timezone() -> None:
    """Test finding next prayer with invalid timezone."""
    calendar = [{}]
    tz = ZoneInfo("Europe/Paris")
    current_time = datetime(2025, 4, 10, 12, 0, tzinfo=tz)

    index, prayer_time = utils.find_next_prayer(
        current_time, calendar, "Invalid/Timezone"
    )
    assert index is None
    assert prayer_time is None


# --- get_regular_prayer_time ---


@freeze_time("2025-04-10 12:00:00+02:00")
@pytest.mark.parametrize(
    ("prayer_data", "expect_datetime"),
    [
        (
            {
                "calendar": [
                    {"10": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"]}
                    for _ in range(12)
                ],
                "timezone": "Europe/Paris",
            },
            True,
        ),  # we manually generate a calendar here we'll be moving this to conftest.py later
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


# --- get_shuruq_time ---


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


# --- get_jumua_time ---


def test_get_jumua_time_success() -> None:
    """Test getting jumua time successfully."""
    prayer_data = {"timezone": "Europe/Paris", "jumua": "13:00"}
    result = utils.get_jumua_time(prayer_data, "jumua")
    assert result is not None
    assert isinstance(result, datetime)


def test_get_jumua_time_no_timezone() -> None:
    """Test getting jumua time without timezone."""
    prayer_data = {"jumua": "13:00"}
    result = utils.get_jumua_time(prayer_data, "jumua")
    assert result is None


def test_get_jumua_time_no_jumua() -> None:
    """Test getting jumua time without jumua data."""
    prayer_data = {"timezone": "Europe/Paris"}
    result = utils.get_jumua_time(prayer_data, "jumua")
    assert result is None


# --- parse_iqama_time ---


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
    [
        "",
        "invalid",
        "5:30",  # single digit hour
        "05:3",  # single digit minute
    ],
)
def test_parse_iqama_time_returns_none(iqama_time) -> None:
    """Test parse_iqama_time with invalid/empty formats returns None."""
    assert utils.parse_iqama_time("05:30", iqama_time) is None


# --- get_iqama_time ---


@freeze_time("2025-04-10 12:00:00+02:00")
@pytest.mark.parametrize(
    ("iqama_day_data", "expected_hour", "expected_minute"),
    [
        (
            ["05:45", "13:00", "16:00", "19:00", "21:00"],
            3,
            45,
        ),  # absolute: 05:45 Paris = 03:45 UTC
        (
            ["+10", "+15", "+10", "+5", "+10"],
            3,
            40,
        ),  # offset: 05:30+10m Paris = 03:40 UTC
    ],
)
def test_get_iqama_time_formats(iqama_day_data, expected_hour, expected_minute) -> None:
    """Test get_iqama_time with absolute and offset iqama formats."""
    calendar = [{} for _ in range(12)]
    calendar[3] = {"10": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"]}
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
        {},  # missing all fields
        {
            "calendar": [{}],
            "iqamaCalendar": [{}],
            "timezone": "Europe/Paris",
        },  # no day data in either calendar
        {  # prayer time found, iqama data missing
            "calendar": [
                {"10": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"]}
                if i == 3
                else {}
                for i in range(12)
            ],
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
    """Test getting iqama time when parse_iqama_time returns None."""
    month_data = {
        "10": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"],
    }
    iqama_month_data = {
        "10": ["+10", "+15", "+10", "+5", "+10"],
    }
    calendar = [{} for _ in range(12)]
    calendar[3] = month_data
    iqama_calendar = [{} for _ in range(12)]
    iqama_calendar[3] = iqama_month_data

    prayer_data = {
        "calendar": calendar,
        "iqamaCalendar": iqama_calendar,
        "timezone": "Europe/Paris",
    }
    with patch(
        "homeassistant.components.mawaqit.utils.parse_iqama_time",
        return_value=None,
    ):
        result = utils.get_iqama_time(prayer_data, "Fajr")
        assert result is None


@freeze_time("2025-04-10 12:00:00+02:00")
def test_get_regular_prayer_time_invalid_timezone() -> None:
    """Test getting regular prayer time with None timezone from time_with_timezone."""
    month_data = {
        "10": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"],
    }
    calendar = [{} for _ in range(12)]
    calendar[3] = month_data

    prayer_data = {"calendar": calendar, "timezone": "Europe/Paris"}
    with patch(
        "homeassistant.components.mawaqit.utils.time_with_timezone",
        return_value=None,
    ):
        result = utils.get_regular_prayer_time(prayer_data, "Fajr")
        assert result is None


@freeze_time("2025-04-10 12:00:00+02:00")
def test_get_shuruq_time_invalid_localization() -> None:
    """Test getting shuruq time when localization fails."""
    prayer_data = {"timezone": "Europe/Paris", "shuruq": "06:45"}
    with patch(
        "homeassistant.components.mawaqit.utils.time_with_timezone",
        return_value=None,
    ):
        result = utils.get_shuruq_time(prayer_data)
        assert result is None


def test_get_jumua_time_invalid_localization() -> None:
    """Test getting jumua time when localization fails."""
    prayer_data = {"timezone": "Europe/Paris", "jumua": "13:00"}
    with patch(
        "homeassistant.components.mawaqit.utils.time_with_timezone",
        return_value=None,
    ):
        result = utils.get_jumua_time(prayer_data, "jumua")
        assert result is None


def test_extract_time_key_error() -> None:
    """Test extract_time_from_calendar handles KeyError."""
    mock_month = MagicMock()
    mock_month.get = MagicMock(side_effect=KeyError("missing"))
    calendar_with_error = [mock_month]
    target_date = date(2025, 1, 1)
    result = utils.extract_time_from_calendar(calendar_with_error, "Fajr", target_date)
    assert result is None


def test_extract_time_value_error() -> None:
    """Test extract_time_from_calendar handles ValueError."""

    class FailIndexList(list):
        """List that raises ValueError on index()."""

        def index(self, value, *args):
            raise ValueError("not found")

    month_data = {"1": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"]}
    calendar = [month_data]
    target_date = date(2025, 1, 1)

    # Patch PRAYER_NAMES with a list whose .index() raises ValueError
    with patch(
        "homeassistant.components.mawaqit.utils.PRAYER_NAMES",
        new=FailIndexList(["fajr", "shuruq", "dhuhr", "asr", "maghrib", "isha"]),
    ):
        result = utils.extract_time_from_calendar(calendar, "Fajr", target_date)
        assert result is None


def test_extract_time_index_error() -> None:
    """Test extract_time_from_calendar handles IndexError."""

    class FailGetitemList(list):
        """List that raises IndexError on __getitem__."""

        def __getitem__(self, index):
            raise IndexError("out of range")

    month_data = {
        "1": FailGetitemList(["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"])
    }
    calendar = [month_data]
    target_date = date(2025, 1, 1)

    result = utils.extract_time_from_calendar(calendar, "Fajr", target_date)
    assert result is None


def test_add_minutes_to_time_internal_error() -> None:
    """Test add_minutes_to_time handles internal ValueError/TypeError gracefully."""
    with patch(
        "homeassistant.components.mawaqit.utils.timedelta",
        side_effect=TypeError("mock error"),
    ):
        result = utils.add_minutes_to_time("12:30", "+15")
        assert result is None


@freeze_time("2025-04-10 12:00:00+02:00")
def test_get_iqama_time_invalid_localization() -> None:
    """Test getting iqama time when localization fails."""
    month_data = {
        "10": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"],
    }
    iqama_month_data = {
        "10": ["+10", "+15", "+10", "+5", "+10"],
    }
    calendar = [{} for _ in range(12)]
    calendar[3] = month_data
    iqama_calendar = [{} for _ in range(12)]
    iqama_calendar[3] = iqama_month_data

    prayer_data = {
        "calendar": calendar,
        "iqamaCalendar": iqama_calendar,
        "timezone": "Europe/Paris",
    }
    with patch(
        "homeassistant.components.mawaqit.utils.time_with_timezone",
        return_value=None,
    ):
        result = utils.get_iqama_time(prayer_data, "Fajr")
        assert result is None

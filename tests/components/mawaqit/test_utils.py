"""Tests for the Mawaqit utility functions."""

from datetime import date, datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

from freezegun import freeze_time
import pytest

from homeassistant.components.mawaqit import utils
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_UUID

# --- _to_utc ---


def test_to_utc_empty_string() -> None:
    """Test _to_utc returns None for empty time string."""
    result = utils._to_utc("Europe/Paris", date(2025, 4, 10), "")
    assert result is None


def test_to_utc_none_string() -> None:
    """Test _to_utc returns None for None time string."""
    result = utils._to_utc("Europe/Paris", date(2025, 4, 10), None)
    assert result is None


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


def test_save_mosque_success() -> None:
    """Test saving mosque data successfully."""
    title, data = utils.save_mosque(
        mosque_display_name="My Mosque",
        mosque_id="uuid1",
        mawaqit_token="token",
        lat=48.0,
        longi=2.0,
    )

    assert title == "MAWAQIT - My Mosque"
    assert data[CONF_API_KEY] == "token"
    assert data[CONF_UUID] == "uuid1"
    assert data[CONF_LATITUDE] == 48.0
    assert data[CONF_LONGITUDE] == 2.0


def test_save_mosque_no_coords() -> None:
    """Test saving mosque data without coordinates."""
    title, data = utils.save_mosque(
        mosque_display_name="My Mosque",
        mosque_id="uuid1",
        mawaqit_token="token",
    )

    assert title == "MAWAQIT - My Mosque"
    assert CONF_LATITUDE not in data
    assert CONF_LONGITUDE not in data


def test_save_mosque_no_token() -> None:
    """Test saving mosque data with no token raises ValueError."""
    with pytest.raises(ValueError):
        utils.save_mosque(
            mosque_display_name="My Mosque",
            mosque_id="uuid1",
            mawaqit_token=None,
        )


# --- extract_time_from_calendar ---


def test_extract_time_valid() -> None:
    """Test extracting a valid prayer time from calendar."""
    month_data = {"10": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"]}
    calendar = [{} for _ in range(12)]
    calendar[3] = month_data  # April (month 4, index 3)
    target_date = date(2025, 4, 10)
    result = utils.extract_time_from_calendar(calendar, "Fajr", target_date)
    assert result == "05:30"


def test_extract_time_iqama_mode() -> None:
    """Test extracting iqama time from calendar."""
    month_data = {"10": ["+10", "+15", "+10", "+5", "+10"]}
    calendar = [{} for _ in range(12)]
    calendar[3] = month_data
    target_date = date(2025, 4, 10)
    result = utils.extract_time_from_calendar(
        calendar, "Fajr", target_date, mode_iqama=True
    )
    assert result == "+10"


def test_extract_time_invalid_prayer_name() -> None:
    """Test extracting time with invalid prayer name."""
    calendar = [{"1": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"]}]
    target_date = date(2025, 1, 1)
    result = utils.extract_time_from_calendar(calendar, "InvalidPrayer", target_date)
    assert result is None


def test_extract_time_missing_month() -> None:
    """Test extracting time when month data is missing."""
    calendar = []  # Empty calendar
    target_date = date(2025, 1, 1)
    result = utils.extract_time_from_calendar(calendar, "Fajr", target_date)
    assert result is None


def test_extract_time_missing_day() -> None:
    """Test extracting time when day data is missing."""
    calendar = [{}]  # Month with no days
    target_date = date(2025, 1, 1)
    result = utils.extract_time_from_calendar(calendar, "Fajr", target_date)
    assert result is None


def test_extract_time_incomplete_times() -> None:
    """Test extracting time when times array is incomplete."""
    calendar = [{"1": ["05:30"]}]  # Only 1 time instead of 6
    target_date = date(2025, 1, 1)
    result = utils.extract_time_from_calendar(calendar, "Fajr", target_date)
    assert result is None


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
    result = utils.add_minutes_to_time("12:30", "+15")
    assert result == "12:45"


def test_add_minutes_to_time_none_inputs() -> None:
    """Test adding minutes with None inputs raises ValueError."""
    with pytest.raises(ValueError, match="Both time_str and minutes_str must be"):
        utils.add_minutes_to_time(None, "+15")

    with pytest.raises(ValueError, match="Both time_str and minutes_str must be"):
        utils.add_minutes_to_time("12:30", None)


def test_add_minutes_to_time_invalid_format() -> None:
    """Test adding minutes with invalid format raises ValueError."""
    with pytest.raises(ValueError, match="Invalid minutes format"):
        utils.add_minutes_to_time("12:30", "15")

    with pytest.raises(ValueError, match="Invalid minutes format"):
        utils.add_minutes_to_time("12:30", "+abc")


# --- get_next_friday ---


@freeze_time("2025-04-07")  # Monday
def test_get_next_friday_from_monday() -> None:
    """Test getting next Friday from a Monday."""
    result = utils.get_next_friday()
    assert result == date(2025, 4, 11)


@freeze_time("2025-04-11")  # Friday
def test_get_next_friday_from_friday() -> None:
    """Test getting next Friday from a Friday returns next week's Friday."""
    result = utils.get_next_friday()
    assert result == date(2025, 4, 18)


@freeze_time("2025-04-12")  # Saturday
def test_get_next_friday_from_saturday() -> None:
    """Test getting next Friday from a Saturday."""
    result = utils.get_next_friday()
    assert result == date(2025, 4, 18)


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
def test_get_regular_prayer_time_success() -> None:
    """Test getting regular prayer time successfully."""
    month_data = {
        "10": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"],
    }
    calendar = [{} for _ in range(12)]
    calendar[3] = month_data

    prayer_data = {"calendar": calendar, "timezone": "Europe/Paris"}
    result = utils.get_regular_prayer_time(prayer_data, "Fajr")
    assert result is not None
    assert isinstance(result, datetime)


def test_get_regular_prayer_time_missing_data() -> None:
    """Test getting regular prayer time with missing data."""
    result = utils.get_regular_prayer_time({}, "Fajr")
    assert result is None


@freeze_time("2025-04-10 12:00:00+02:00")
def test_get_regular_prayer_time_no_time_found() -> None:
    """Test getting regular prayer time when time not found in calendar."""
    calendar = [{}]  # Empty month data
    prayer_data = {"calendar": calendar, "timezone": "Europe/Paris"}
    result = utils.get_regular_prayer_time(prayer_data, "Fajr")
    assert result is None


# --- get_shuruq_time ---


@freeze_time("2025-04-10 12:00:00+02:00")
def test_get_shuruq_time_success() -> None:
    """Test getting shuruq time successfully."""
    prayer_data = {"timezone": "Europe/Paris", "shuruq": "06:45"}
    result = utils.get_shuruq_time(prayer_data)
    assert result is not None
    assert isinstance(result, datetime)


def test_get_shuruq_time_no_timezone() -> None:
    """Test getting shuruq time without timezone."""
    prayer_data = {"shuruq": "06:45"}
    result = utils.get_shuruq_time(prayer_data)
    assert result is None


def test_get_shuruq_time_no_shuruq() -> None:
    """Test getting shuruq time without shuruq data."""
    prayer_data = {"timezone": "Europe/Paris"}
    result = utils.get_shuruq_time(prayer_data)
    assert result is None


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


def test_parse_iqama_time_offset_format() -> None:
    """Test parse_iqama_time with +xx offset format."""
    result = utils.parse_iqama_time("05:30", "+10")
    assert result == "05:40"


def test_parse_iqama_time_offset_zero() -> None:
    """Test parse_iqama_time with +0 offset."""
    result = utils.parse_iqama_time("05:30", "+0")
    assert result == "05:30"


def test_parse_iqama_time_absolute_format() -> None:
    """Test parse_iqama_time with HH:MM absolute time format."""
    result = utils.parse_iqama_time("05:30", "06:15")
    assert result == "06:15"


def test_parse_iqama_time_absolute_ignores_prayer_time() -> None:
    """Test that absolute format does not use prayer_time at all."""
    # Different prayer_time shouldn't affect the result
    assert utils.parse_iqama_time("05:30", "06:15") == utils.parse_iqama_time(
        "20:00", "06:15"
    )


def test_parse_iqama_time_empty_string() -> None:
    """Test parse_iqama_time with empty string."""
    result = utils.parse_iqama_time("05:30", "")
    assert result is None


def test_parse_iqama_time_unrecognised_format() -> None:
    """Test parse_iqama_time with unrecognised format logs error and returns None."""
    result = utils.parse_iqama_time("05:30", "invalid")
    assert result is None


def test_parse_iqama_time_unrecognised_format_partial_match() -> None:
    """Test parse_iqama_time rejects partial HH:MM matches like '5:30' or '05:3'."""
    assert utils.parse_iqama_time("05:30", "5:30") is None  # single digit hour
    assert utils.parse_iqama_time("05:30", "05:3") is None  # single digit minute


# --- get_iqama_time ---


@freeze_time("2025-04-10 12:00:00+02:00")
def test_get_iqama_time_absolute_format() -> None:
    """Test getting iqama time when iqama calendar uses HH:MM absolute times."""
    month_data = {
        "10": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"],
    }
    iqama_month_data = {
        "10": ["05:45", "13:00", "16:00", "19:00", "21:00"],  # absolute times
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
    result = utils.get_iqama_time(prayer_data, "Fajr")
    assert result is not None
    assert isinstance(result, datetime)
    # 05:45 Paris (UTC+2) = 03:45 UTC
    assert result.hour == 3
    assert result.minute == 45


@freeze_time("2025-04-10 12:00:00+02:00")
def test_get_iqama_time_offset_format() -> None:
    """Test getting iqama time when iqama is in offset format Successfully."""
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
    result = utils.get_iqama_time(prayer_data, "Fajr")
    assert result is not None
    assert isinstance(result, datetime)


def test_get_iqama_time_missing_data() -> None:
    """Test getting iqama time with missing calendar data."""
    result = utils.get_iqama_time({}, "Fajr")
    assert result is None


@freeze_time("2025-04-10 12:00:00+02:00")
def test_get_iqama_time_no_prayer_time() -> None:
    """Test getting iqama time when prayer time not found."""
    calendar = [{}]
    iqama_calendar = [{}]
    prayer_data = {
        "calendar": calendar,
        "iqamaCalendar": iqama_calendar,
        "timezone": "Europe/Paris",
    }
    result = utils.get_iqama_time(prayer_data, "Fajr")
    assert result is None


@freeze_time("2025-04-10 12:00:00+02:00")
def test_get_iqama_time_no_iqama_offset() -> None:
    """Test getting iqama time when iqama offset not found."""
    month_data = {
        "10": ["05:30", "06:45", "12:30", "15:45", "18:30", "20:00"],
    }
    calendar = [{} for _ in range(12)]
    calendar[3] = month_data
    iqama_calendar = [{}]  # No iqama data

    prayer_data = {
        "calendar": calendar,
        "iqamaCalendar": iqama_calendar,
        "timezone": "Europe/Paris",
    }
    result = utils.get_iqama_time(prayer_data, "Fajr")
    assert result is None


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

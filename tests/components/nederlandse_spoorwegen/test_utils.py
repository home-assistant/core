"""Test utilities for Nederlandse Spoorwegen integration."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from homeassistant.components.nederlandse_spoorwegen.utils import (
    format_time,
    get_current_utc_timestamp,
    get_trip_attribute,
    is_station_cache_valid,
    normalize_and_validate_time_format,
    normalize_station_code,
    validate_route_structure,
    validate_time_format,
)


class TestValidateRouteStructure:
    """Test validate_route_structure function."""

    def test_valid_route_structure(self) -> None:
        """Test valid route structure."""
        route = {
            "from": "UTG",
            "to": "HT",
            "name": "Test Route",
            "via": "",
            "time": "",
        }
        assert validate_route_structure(route) is True

    def test_valid_route_minimal(self) -> None:
        """Test valid route with minimal required fields."""
        route = {"from": "UTG", "to": "HT"}
        assert validate_route_structure(route) is True

    def test_invalid_route_not_dict(self) -> None:
        """Test invalid route - not a dict (regression test for UTG_HT issue)."""
        # This was the exact issue: string passed instead of dict
        route = "UTG_HT"  # type: ignore[arg-type]
        assert validate_route_structure(route) is False  # type: ignore  # noqa: PGH003

    def test_invalid_route_missing_from(self) -> None:
        """Test invalid route - missing 'from' field."""
        route = {"to": "HT", "name": "Test Route"}
        assert validate_route_structure(route) is False

    def test_invalid_route_missing_to(self) -> None:
        """Test invalid route - missing 'to' field."""
        route = {"from": "UTG", "name": "Test Route"}
        assert validate_route_structure(route) is False

    def test_invalid_route_empty_from(self) -> None:
        """Test invalid route - empty 'from' field."""
        route = {"from": "", "to": "HT"}
        assert validate_route_structure(route) is False

    def test_invalid_route_empty_to(self) -> None:
        """Test invalid route - empty 'to' field."""
        route = {"from": "UTG", "to": ""}
        assert validate_route_structure(route) is False

    def test_invalid_route_none_values(self) -> None:
        """Test invalid route - None values."""
        route = {"from": None, "to": "HT"}
        assert validate_route_structure(route) is False

        route = {"from": "UTG", "to": None}
        assert validate_route_structure(route) is False


class TestNormalizeStationCode:
    """Test normalize_station_code function."""

    def test_normalize_valid_code(self) -> None:
        """Test normalizing valid station codes converts to uppercase."""
        assert normalize_station_code("utg") == "UTG"
        assert normalize_station_code("ht") == "HT"
        assert normalize_station_code("AMS") == "AMS"
        assert normalize_station_code("Asd") == "ASD"

    def test_normalize_with_whitespace(self) -> None:
        """Test normalizing codes with whitespace (removes whitespace and converts to uppercase)."""
        assert normalize_station_code(" utg ") == "UTG"
        assert normalize_station_code("\tht\n") == "HT"

    def test_normalize_empty_or_none(self) -> None:
        """Test normalizing empty or None values."""
        assert normalize_station_code("") == ""
        assert normalize_station_code(None) == ""
        assert normalize_station_code("   ") == ""

    def test_normalize_non_string(self) -> None:
        """Test normalizing non-string values."""
        assert normalize_station_code(str(123)) == "123"


class TestValidateTimeFormat:
    """Test time format validation functions."""

    def test_validate_time_format_valid(self) -> None:
        """Test valid time formats."""
        assert validate_time_format("08:30") is True
        assert validate_time_format("23:59") is True
        assert validate_time_format("00:00") is True
        assert validate_time_format("12:30:45") is True

    def test_validate_time_format_invalid(self) -> None:
        """Test invalid time formats."""
        assert validate_time_format("25:00") is False
        assert validate_time_format("12:60") is False
        assert validate_time_format("12:30:60") is False
        assert validate_time_format("not_a_time") is False
        assert validate_time_format("12") is False

    def test_validate_time_format_none_or_empty(self) -> None:
        """Test None or empty time formats."""
        assert validate_time_format(None) is True
        assert validate_time_format("") is True

    def test_normalize_and_validate_time_format_valid(self) -> None:
        """Test normalize and validate with valid formats."""
        is_valid, normalized = normalize_and_validate_time_format("08:30")
        assert is_valid is True
        assert normalized == "08:30:00"

        is_valid, normalized = normalize_and_validate_time_format("8:5")
        assert is_valid is True
        assert normalized == "08:05:00"

        is_valid, normalized = normalize_and_validate_time_format("12:30:45")
        assert is_valid is True
        assert normalized == "12:30:45"

    def test_normalize_and_validate_time_format_invalid(self) -> None:
        """Test normalize and validate with invalid formats."""
        is_valid, normalized = normalize_and_validate_time_format("25:00")
        assert is_valid is False
        assert normalized is None

        is_valid, normalized = normalize_and_validate_time_format("not_a_time")
        assert is_valid is False
        assert normalized is None

    def test_normalize_and_validate_time_format_none(self) -> None:
        """Test normalize and validate with None input."""
        is_valid, normalized = normalize_and_validate_time_format(None)
        assert is_valid is True
        assert normalized is None


class TestFormatTime:
    """Test format_time function."""

    def test_format_valid_datetime(self) -> None:
        """Test formatting valid datetime."""
        dt = datetime(2023, 12, 1, 14, 30, 0)
        result = format_time(dt)
        assert result == "14:30"

    def test_format_none_datetime(self) -> None:
        """Test formatting None datetime."""
        result = format_time(None)
        assert result is None

    def test_format_invalid_input(self) -> None:
        """Test formatting invalid input."""
        result = format_time(123)  # type: ignore[arg-type]
        assert result is None


class TestGetTripAttribute:
    """Test get_trip_attribute function."""

    def test_get_valid_attribute(self) -> None:
        """Test getting valid attribute from trip object."""
        trip = MagicMock()
        trip.test_attr = "test_value"

        result = get_trip_attribute(trip, "test_attr")
        assert result == "test_value"

    def test_get_missing_attribute(self) -> None:
        """Test getting missing attribute returns None."""

        # Use a real object instead of MagicMock to test missing attribute
        class TestObject:
            pass

        trip = TestObject()
        result = get_trip_attribute(trip, "missing_attr")
        assert result is None

    def test_get_attribute_none_trip(self) -> None:
        """Test getting attribute from None trip."""
        result = get_trip_attribute(None, "test_attr")
        assert result is None

    def test_get_attribute_empty_name(self) -> None:
        """Test getting attribute with empty name."""
        trip = MagicMock()

        result = get_trip_attribute(trip, "")
        assert result is None

    def test_get_attribute_invalid_name(self) -> None:
        """Test getting attribute with invalid name."""
        trip = MagicMock()

        result = get_trip_attribute(trip, "invalid@name")
        assert result is None


class TestStationCacheValidation:
    """Test station cache validation functions."""

    def test_is_station_cache_valid_recent(self) -> None:
        """Test cache validation with recent timestamp."""
        recent_time = datetime.now(UTC).isoformat()
        result = is_station_cache_valid(recent_time)
        assert result is True

    def test_is_station_cache_valid_old(self) -> None:
        """Test cache validation with old timestamp."""
        old_time = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        result = is_station_cache_valid(old_time)
        assert result is False

    def test_is_station_cache_valid_none(self) -> None:
        """Test cache validation with None timestamp."""
        result = is_station_cache_valid(None)
        assert result is False

    def test_is_station_cache_valid_invalid_format(self) -> None:
        """Test cache validation with invalid timestamp format."""
        result = is_station_cache_valid("invalid_timestamp")
        assert result is False


class TestUtcTimestamp:
    """Test UTC timestamp function."""

    def test_get_current_utc_timestamp(self) -> None:
        """Test getting current UTC timestamp."""
        result = get_current_utc_timestamp()
        assert isinstance(result, str)
        assert "T" in result  # ISO format includes T
        assert result.endswith(("+00:00", "Z"))  # UTC timezone

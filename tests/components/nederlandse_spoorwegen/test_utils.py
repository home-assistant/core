"""Test Nederlandse Spoorwegen utility functions."""

from datetime import UTC, datetime, timedelta

from homeassistant.components.nederlandse_spoorwegen.utils import (
    format_time,
    generate_route_key,
    get_current_utc_timestamp,
    get_trip_attribute,
    is_station_cache_valid,
    normalize_and_validate_time_format,
    normalize_station_code,
    safe_get_nested_value,
    safe_int_conversion,
    safe_str_conversion,
    validate_route_structure,
    validate_time_format,
)


class TestTimeValidation:
    """Test time validation utilities."""

    def test_normalize_and_validate_time_format_valid(self):
        """Test time format normalization with valid inputs."""
        # Test HH:MM format
        is_valid, normalized = normalize_and_validate_time_format("14:30")
        assert is_valid is True
        assert normalized == "14:30:00"

        # Test HH:MM:SS format
        is_valid, normalized = normalize_and_validate_time_format("14:30:45")
        assert is_valid is True
        assert normalized == "14:30:45"

        # Test None input
        is_valid, normalized = normalize_and_validate_time_format(None)
        assert is_valid is True
        assert normalized is None

    def test_normalize_and_validate_time_format_invalid(self):
        """Test time format normalization with invalid inputs."""
        # Test invalid format
        is_valid, normalized = normalize_and_validate_time_format("25:30")
        assert is_valid is False
        assert normalized is None

        # Test invalid minutes
        is_valid, normalized = normalize_and_validate_time_format("14:70")
        assert is_valid is False
        assert normalized is None

        # Test invalid format structure
        is_valid, normalized = normalize_and_validate_time_format("14")
        assert is_valid is False
        assert normalized is None

    def test_validate_time_format(self):
        """Test backward compatible time validation."""
        assert validate_time_format("14:30") is True
        assert validate_time_format("25:30") is False
        assert validate_time_format(None) is True


class TestTimeFormatting:
    """Test time formatting utilities."""

    def test_format_time_valid(self):
        """Test time formatting with valid datetime."""
        dt = datetime(2023, 1, 1, 14, 30, 45)
        assert format_time(dt) == "14:30"

    def test_format_time_invalid(self):
        """Test time formatting with invalid inputs."""
        assert format_time(None) is None
        # Test with non-datetime object (the function handles this gracefully)
        result = format_time("not_a_datetime")  # type: ignore[arg-type]
        assert result is None


class TestStationCache:
    """Test station cache utilities."""

    def test_is_station_cache_valid_recent(self):
        """Test cache validation with recent timestamp."""
        recent_time = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        assert is_station_cache_valid(recent_time) is True

    def test_is_station_cache_valid_old(self):
        """Test cache validation with old timestamp."""
        old_time = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        assert is_station_cache_valid(old_time) is False

    def test_is_station_cache_valid_invalid(self):
        """Test cache validation with invalid inputs."""
        assert is_station_cache_valid(None) is False
        assert is_station_cache_valid("invalid") is False


class TestRouteValidation:
    """Test route validation utilities."""

    def test_validate_route_structure_valid(self):
        """Test route validation with valid structure."""
        route = {"from": "AMS", "to": "UT"}
        assert validate_route_structure(route) is True

    def test_validate_route_structure_invalid(self):
        """Test route validation with invalid structure."""
        assert validate_route_structure({}) is False
        assert validate_route_structure({"from": "AMS"}) is False
        # Test with non-dict input (the function handles this gracefully)
        result = validate_route_structure("not_a_dict")  # type: ignore[arg-type]
        assert result is False


class TestRouteKeyGeneration:
    """Test route key generation utilities."""

    def test_generate_route_key_valid(self):
        """Test route key generation with valid route."""
        route = {"from": "AMS", "to": "UT"}
        assert generate_route_key(route) == "AMS_UT"

    def test_generate_route_key_invalid(self):
        """Test route key generation with invalid route."""
        assert generate_route_key({}) is None
        assert generate_route_key({"from": "AMS"}) is None


class TestStationNormalization:
    """Test station code normalization."""

    def test_normalize_station_code_valid(self):
        """Test station code normalization."""
        assert normalize_station_code("ams") == "AMS"
        assert normalize_station_code(" ut ") == "UT"
        assert normalize_station_code("Amsterdam") == "AMSTERDAM"

    def test_normalize_station_code_invalid(self):
        """Test station code normalization with invalid input."""
        assert normalize_station_code(None) == ""
        assert normalize_station_code("") == ""


class TestTripAttributes:
    """Test trip attribute utilities."""

    def test_get_trip_attribute_valid(self):
        """Test getting trip attributes with valid inputs."""

        class MockTrip:
            departure_time = "14:30"
            platform = "3"

        trip = MockTrip()
        assert get_trip_attribute(trip, "departure_time") == "14:30"
        assert get_trip_attribute(trip, "platform") == "3"

    def test_get_trip_attribute_invalid(self):
        """Test getting trip attributes with invalid inputs."""

        class MockTrip:
            departure_time = "14:30"

        trip = MockTrip()
        assert get_trip_attribute(trip, "nonexistent") is None
        assert get_trip_attribute(None, "departure_time") is None
        # Test with None attribute name (the function handles this gracefully)
        result = get_trip_attribute(trip, None)  # type: ignore[arg-type]
        assert result is None
        assert get_trip_attribute(trip, "invalid_chars!") is None


class TestSafeUtilities:
    """Test safe conversion utilities."""

    def test_safe_get_nested_value_valid(self):
        """Test safe nested value extraction."""
        data = {"level1": {"level2": {"value": "test"}}}
        assert safe_get_nested_value(data, "level1", "level2", "value") == "test"

    def test_safe_get_nested_value_invalid(self):
        """Test safe nested value extraction with invalid paths."""
        data = {"level1": {"level2": {"value": "test"}}}
        assert safe_get_nested_value(data, "missing", "level2", "value") is None
        assert safe_get_nested_value(data, "level1", "missing", "value") is None

    def test_safe_int_conversion(self):
        """Test safe integer conversion."""
        assert safe_int_conversion("123") == 123
        assert safe_int_conversion("invalid", default=42) == 42
        assert safe_int_conversion(None) == 0

    def test_safe_str_conversion(self):
        """Test safe string conversion."""
        assert safe_str_conversion(123) == "123"
        assert safe_str_conversion(None, default="empty") == "empty"
        assert safe_str_conversion("test") == "test"


class TestTimestampUtility:
    """Test timestamp utility."""

    def test_get_current_utc_timestamp(self):
        """Test UTC timestamp generation."""
        timestamp = get_current_utc_timestamp()
        assert isinstance(timestamp, str)
        # Should be able to parse back to datetime
        parsed = datetime.fromisoformat(timestamp)
        assert parsed.tzinfo == UTC

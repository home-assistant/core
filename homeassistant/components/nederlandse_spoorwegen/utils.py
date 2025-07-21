"""Utility functions for Nederlandse Spoorwegen integration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

# Constants
STATION_CACHE_DURATION = timedelta(days=1)


def normalize_and_validate_time_format(time_str: str | None) -> tuple[bool, str | None]:
    """Normalize and validate time format, returning (is_valid, normalized_time).

    Accepts HH:MM or HH:MM:SS format and normalizes to HH:MM:SS.
    """
    if not time_str:
        return True, None  # Optional field

    try:
        # Basic validation for HH:MM or HH:MM:SS format
        parts = time_str.split(":")
        if len(parts) == 2:
            # Add seconds if not provided
            hours, minutes = parts
            seconds = "00"
        elif len(parts) == 3:
            hours, minutes, seconds = parts
        else:
            return False, None

        # Validate ranges
        if not (
            0 <= int(hours) <= 23
            and 0 <= int(minutes) <= 59
            and 0 <= int(seconds) <= 59
        ):
            return False, None

        # Return normalized format HH:MM:SS
        normalized = f"{int(hours):02d}:{int(minutes):02d}:{int(seconds):02d}"
    except (ValueError, AttributeError):
        return False, None
    else:
        return True, normalized


def validate_time_format(time_str: str | None) -> bool:
    """Validate time format (backward compatibility)."""
    is_valid, _ = normalize_and_validate_time_format(time_str)
    return is_valid


def format_time(dt: datetime | None) -> str | None:
    """Format datetime to HH:MM string with proper error handling."""
    if not dt or not isinstance(dt, datetime):
        return None

    try:
        return dt.strftime("%H:%M")
    except (ValueError, OSError) as ex:
        _LOGGER.debug("Failed to format datetime %s: %s", dt, ex)
        return None


def get_trip_attribute(trip: Any, attr_name: str) -> Any:
    """Get attribute from trip object safely with validation."""
    if not trip or not attr_name:
        return None

    try:
        # Validate attribute name to prevent injection
        if not isinstance(attr_name, str) or not attr_name.replace("_", "").isalnum():
            _LOGGER.debug("Invalid attribute name: %s", attr_name)
            return None

        return getattr(trip, attr_name, None)
    except (AttributeError, TypeError) as ex:
        _LOGGER.debug("Failed to get attribute %s from trip: %s", attr_name, ex)
        return None


def is_station_cache_valid(stations_updated: str | None) -> bool:
    """Check if station cache is still valid."""
    if not stations_updated:
        return False

    try:
        if isinstance(stations_updated, str):
            updated_dt = datetime.fromisoformat(stations_updated)
            return (datetime.now(UTC) - updated_dt) <= STATION_CACHE_DURATION
    except (ValueError, TypeError) as ex:
        _LOGGER.debug("Invalid stations_updated timestamp format: %s", ex)

    return False


def get_current_utc_timestamp() -> str:
    """Get current UTC timestamp as ISO format string."""
    return datetime.now(UTC).isoformat()


def validate_route_structure(route: dict[str, Any]) -> bool:
    """Validate if route has required structure."""
    if not isinstance(route, dict):
        return False

    required_fields = ["from", "to"]
    return all(field in route and route[field] for field in required_fields)


def normalize_station_code(station_code: str | None) -> str:
    """Normalize station code to uppercase."""
    if not station_code:
        return ""
    return str(station_code).upper().strip()


def generate_route_key(route: dict[str, Any]) -> str | None:
    """Generate a unique key for a route configuration."""
    if not validate_route_structure(route):
        return None

    from_station = normalize_station_code(route.get("from"))
    to_station = normalize_station_code(route.get("to"))

    if not from_station or not to_station:
        return None

    return f"{from_station}_{to_station}"


def safe_get_nested_value(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely get nested dictionary value with multiple keys."""
    current = data

    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]

    return current


def is_list_of_dicts(data: Any) -> bool:
    """Check if data is a list containing dictionaries."""
    return (
        isinstance(data, list)
        and len(data) > 0
        and all(isinstance(item, dict) for item in data)
    )


def safe_int_conversion(value: Any, default: int = 0) -> int:
    """Safely convert value to integer with fallback."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_str_conversion(value: Any, default: str = "") -> str:
    """Safely convert value to string with fallback."""
    try:
        return str(value) if value is not None else default
    except (ValueError, TypeError):
        return default

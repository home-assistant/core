"""Utility functions for the School Holiday integration."""

from datetime import date, datetime
import re
from typing import Any

from .const import COUNTRY_NAMES, LOGGER, REGION_NAMES


def clean_string(value: str | None) -> str | None:
    """Clean a value by removing all HTML character entities and stripping leading/trailing whitespace."""
    if value is None:
        return None

    return re.sub(r"&[a-zA-Z0-9#]+;", "", value).strip()


def create_calendar_event(
    events: list[dict[str, Any]],
    summary: str,
    start: date,
    end: date,
    description: str | None,
) -> None:
    """Create and append a calendar event."""
    LOGGER.debug(
        "Adding school holiday '%s' from %s to %s",
        summary,
        start,
        end,
    )

    events.append(
        {
            "summary": summary,
            "start": start,
            "end": end,
            "description": description,
        }
    )


def ensure_date(value: str | date) -> date:
    """Ensure a value is a date (without time)."""
    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            # Parse as datetime, then get date.
            return datetime.fromisoformat(value).date()
        except ValueError:
            # Fallback to date string.
            return date.fromisoformat(value)
    raise TypeError(f"Value {value} must be a string or date, but got {type(value)}")


def get_device_name(country_code: str, region_code: str) -> str:
    """Get the device name from country and region codes.

    Device names should remain consistent across languages for proper device grouping.
    """
    country_name = COUNTRY_NAMES.get(country_code, country_code)
    region_name = REGION_NAMES.get(country_code, {}).get(region_code, region_code)
    return f"{country_name} - {region_name}"

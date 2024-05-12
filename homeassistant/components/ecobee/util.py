"""Validation utility functions for ecobee services."""

from datetime import date, datetime, timedelta

import voluptuous as vol


def ecobee_date(date_string):
    """Validate a date_string as valid for the ecobee API."""
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
    except ValueError as err:
        raise vol.Invalid("Date does not match ecobee date format YYYY-MM-DD") from err
    return date_string


def ecobee_time(time_string):
    """Validate a time_string as valid for the ecobee API."""
    try:
        datetime.strptime(time_string, "%H:%M:%S")
    except ValueError as err:
        raise vol.Invalid(
            "Time does not match ecobee 24-hour time format HH:MM:SS"
        ) from err
    return time_string


def is_indefinite_hold(start_date_string: str, end_date_string: str) -> bool:
    """Determine if the given start and end dates from the ecobee API represent an indefinite hold.

    This is not documented in the API, so a rough heuristic is used where a hold over 1 year is considered indefinite.
    """
    return date.fromisoformat(end_date_string) - date.fromisoformat(
        start_date_string
    ) > timedelta(days=365)

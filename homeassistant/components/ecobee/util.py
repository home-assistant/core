"""Validation utility functions for ecobee services."""
from datetime import datetime

import voluptuous as vol


def ecobee_date(date_string):
    """Validate a date_string as valid for the ecobee API."""
    try:
        datetime.strptime(date_string, "%Y-%m-%d")
    except ValueError:
        raise vol.Invalid("Date does not match ecobee date format YYYY-MM-DD")
    return date_string


def ecobee_time(time_string):
    """Validate a time_string as valid for the ecobee API."""
    try:
        datetime.strptime(time_string, "%H:%M:%S")
    except ValueError:
        raise vol.Invalid("Time does not match ecobee 24-hour time format HH:MM:SS")
    return time_string

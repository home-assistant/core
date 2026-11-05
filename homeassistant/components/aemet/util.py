"""Utility functions for the AEMET OpenData integration."""

from datetime import date, datetime
from typing import Any

from homeassistant.util import dt as dt_util


def parse_issue_date(value: Any) -> date | None:
    """Parse a stored API key issue date."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return dt_util.parse_date(value)

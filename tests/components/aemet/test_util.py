"""Define tests for the AEMET utility functions."""

from datetime import date, datetime

from homeassistant.components.aemet.util import parse_issue_date


def test_parse_issue_date() -> None:
    """Test parsing API key issue dates."""
    assert parse_issue_date(None) is None
    assert parse_issue_date("") is None
    assert parse_issue_date(datetime(2021, 1, 1, 12, 0)) == date(2021, 1, 1)
    assert parse_issue_date(date(2021, 1, 1)) == date(2021, 1, 1)
    assert parse_issue_date("2021-01-01") == date(2021, 1, 1)
    assert parse_issue_date("invalid") is None

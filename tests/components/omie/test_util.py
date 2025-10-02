"""Test the OMIE util module."""

from zoneinfo import ZoneInfo

from freezegun import freeze_time
import pytest

from homeassistant.components.omie.util import current_quarter_hour_cet


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        # UTC on the left, CET on the right (after normalized)
        ("2025-05-21T22:44:59Z", "2025-05-22T00:30:00+02:00"),
        ("2024-01-15T12:01:31Z", "2024-01-15T13:00:00+01:00"),
        ("2024-01-15T00:00:00Z", "2024-01-15T01:00:00+01:00"),
        ("2025-10-26T02:10:01Z", "2025-10-26T03:00:00+01:00"),
        ("2025-10-26T03:26:01Z", "2025-10-26T04:15:00+01:00"),
        ("2027-02-03T03:53:35Z", "2027-02-03T04:45:00+01:00"),
    ],
)
def test_current_quarter_hour_cet(now: str, expected: str) -> None:
    """Tests that current_quarter_hour_cet rounds down to the nearest 1/4 hour."""
    with freeze_time(now):
        start_time = current_quarter_hour_cet()
        assert start_time.isoformat() == expected
        assert start_time.tzinfo == ZoneInfo("CET")

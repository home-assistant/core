"""Test the OMIE util module."""

from zoneinfo import ZoneInfo

from freezegun import freeze_time
import pytest

from homeassistant.components.omie.util import current_quarter_hour_cet


@pytest.mark.parametrize(
    # UTC on the left, CET on the right (after normalized)
    ("now_utc", "expected_cet"),
    [
        # CEST (UTC+2h). DST active.
        ("2025-05-21T22:44:59Z", "2025-05-22T00:30:00+02:00"),
        ("2025-10-26T00:35:21Z", "2025-10-26T02:30:00+02:00"),
        # Back to CET (UTC+1h) on 26 October 2025 at 3 AM. DST ended.
        ("2025-10-26T01:40:54Z", "2025-10-26T02:30:00+01:00"),
        ("2025-10-26T01:50:45Z", "2025-10-26T02:45:00+01:00"),
        ("2025-11-15T15:25:31Z", "2025-11-15T16:15:00+01:00"),
        ("2026-03-29T00:05:21Z", "2026-03-29T01:00:00+01:00"),
        # On to CEST (UTC+2h) for summer on 29 March 2026 at 2 AM. DST started again.
        ("2026-03-29T01:14:31Z", "2026-03-29T03:00:00+02:00"),
    ],
)
def test_current_quarter_hour_cet(now_utc: str, expected_cet: str) -> None:
    """Tests that current_quarter_hour_cet rounds down to the nearest 1/4 hour."""
    with freeze_time(now_utc, tz_offset=0):
        start_time = current_quarter_hour_cet()
        assert start_time.isoformat() == expected_cet
        assert start_time.tzinfo == ZoneInfo("CET")

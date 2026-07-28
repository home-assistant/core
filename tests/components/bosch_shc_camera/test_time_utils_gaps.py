"""Tests for `time_utils.parse_bosch_timestamp`'s timezone-aware parsing."""

from datetime import UTC, datetime

import pytest

from homeassistant.components.bosch_shc_camera.time_utils import parse_bosch_timestamp


@pytest.mark.parametrize(
    ("ts_str", "expected"),
    [
        pytest.param(None, None, id="none"),
        pytest.param("", None, id="empty-string"),
        pytest.param("not-a-timestamp", None, id="unparsable"),
        pytest.param(
            "2026-06-18T06:06:30.499+02:00[Europe/Berlin]",
            datetime(2026, 6, 18, 4, 6, 30, 499000, tzinfo=UTC),
            id="offset-with-rfc9557-zone-bracket",
        ),
        pytest.param(
            "2026-03-22T14:30:00.000Z",
            datetime(2026, 3, 22, 14, 30, 0, tzinfo=UTC),
            id="zulu-suffix",
        ),
        pytest.param(
            "2026-03-19T09:32:08",
            datetime(2026, 3, 19, 9, 32, 8, tzinfo=UTC),
            id="naive-assumed-utc",
        ),
    ],
)
def test_parse_bosch_timestamp(ts_str: str | None, expected: datetime | None) -> None:
    """Every observed Bosch timestamp format parses to the correct UTC instant."""
    assert parse_bosch_timestamp(ts_str) == expected

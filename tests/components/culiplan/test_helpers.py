"""Tests for the small helper module."""

from datetime import UTC, datetime

import pytest

from homeassistant.components.culiplan.const import DOMAIN
from homeassistant.components.culiplan.helpers import build_device_info, parse_dt

from tests.common import MockConfigEntry


def test_build_device_info() -> None:
    """The DeviceInfo carries the expected static fields."""
    entry = MockConfigEntry(domain=DOMAIN, entry_id="abc")
    info = build_device_info(entry)
    assert info["name"] == "Culiplan"
    assert (DOMAIN, "abc") in info["identifiers"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2099-01-15T18:00:00Z", datetime(2099, 1, 15, 18, 0, tzinfo=UTC)),
        ("2099-01-15", datetime(2099, 1, 15, 0, 0, tzinfo=UTC)),
        ("2099-01-15T18:00:00+00:00", datetime(2099, 1, 15, 18, 0, tzinfo=UTC)),
    ],
)
def test_parse_dt_valid(value: str, expected: datetime) -> None:
    """Valid ISO strings parse to tz-aware datetimes."""
    assert parse_dt(value) == expected


def test_parse_dt_invalid() -> None:
    """Invalid strings raise ValueError."""
    with pytest.raises(ValueError):
        parse_dt("not-a-date")

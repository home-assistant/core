"""Huawei LTE sensor tests."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.huawei_lte import sensor
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)
from homeassistant.util import dt as dt_util


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("-71 dBm", (-71, SIGNAL_STRENGTH_DECIBELS_MILLIWATT)),
        ("15dB", (15, SIGNAL_STRENGTH_DECIBELS)),
        (">=-51dBm", (-51, SIGNAL_STRENGTH_DECIBELS_MILLIWATT)),
        ("&lt;-20dB", (-20, SIGNAL_STRENGTH_DECIBELS)),
        ("&gt;=30dB", (30, SIGNAL_STRENGTH_DECIBELS)),
    ],
)
def test_format_default(value, expected) -> None:
    """Test that default formatter copes with expected values."""
    assert sensor.format_default(value) == expected


@pytest.mark.parametrize(
    ("value", "expected_elapsed"),
    [
        ("0", timedelta(0)),
        ("90", timedelta(seconds=90)),
        ("86400", timedelta(days=1)),
    ],
)
def test_format_last_reset_elapsed_seconds(
    freezer: FrozenDateTimeFactory, value: str, expected_elapsed: timedelta
) -> None:
    """Test elapsed seconds are turned into an aware, truncated reset time."""
    freezer.move_to("2026-01-02T03:04:05.678901+00:00")

    result = sensor.format_last_reset_elapsed_seconds(value)

    assert result is not None
    assert result.tzinfo is not None
    assert result.microsecond == 0
    assert result == dt_util.utcnow().replace(microsecond=0) - expected_elapsed


@pytest.mark.parametrize("value", [None, "", "not a number"])
def test_format_last_reset_elapsed_seconds_invalid(value: str | None) -> None:
    """Test values that cannot be converted are ignored."""
    assert sensor.format_last_reset_elapsed_seconds(value) is None

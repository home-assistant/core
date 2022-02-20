"""Huawei LTE sensor tests."""

import pytest

from homeassistant.components.huawei_lte import sensor
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("-71 dBm", (-71, SIGNAL_STRENGTH_DECIBELS_MILLIWATT)),
        ("15dB", (15, SIGNAL_STRENGTH_DECIBELS)),
        (">=-51dBm", (-51, SIGNAL_STRENGTH_DECIBELS_MILLIWATT)),
    ),
)
def test_format_default(value, expected):
    """Test that default formatter copes with expected values."""
    assert sensor.format_default(value) == expected

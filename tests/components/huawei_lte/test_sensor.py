"""Huawei LTE sensor tests."""

import pytest

from homeassistant.components.huawei_lte import sensor


@pytest.mark.parametrize(
    ("value", "expected"),
    (("-71 dBm", (-71, "dBm")), ("15dB", (15, "dB")), (">=-51dBm", (-51, "dBm"))),
)
def test_format_default(value, expected):
    """Test that default formatter copes with expected values."""
    assert sensor.format_default(value) == expected

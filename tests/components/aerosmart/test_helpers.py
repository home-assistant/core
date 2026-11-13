"""Tests for the aerosmart helpers."""

import pytest

from homeassistant.components.aerosmart.helpers import format_device_type


@pytest.mark.parametrize(
    ("device_type", "expected"),
    [
        pytest.param(4, "aerosmart s", id="s"),
        pytest.param(5, "aerosmart m", id="m"),
        pytest.param(6, "aerosmart l", id="l"),
        pytest.param(7, "aerosmart xls", id="xls"),
        pytest.param(11, "aerosmart mono", id="mono"),
        pytest.param(3, "3", id="unknown"),
    ],
)
def test_format_device_type(device_type: int, expected: str) -> None:
    """Known aerosmart types use product names and unknown types keep their code."""
    assert format_device_type(device_type) == expected

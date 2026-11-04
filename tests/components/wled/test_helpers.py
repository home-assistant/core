"""Tests for the WLED helpers."""

import pytest

from homeassistant.components.wled.helpers import cct_to_kelvin, kelvin_to_cct


@pytest.mark.parametrize(
    ("kelvin", "cct"),
    [
        pytest.param(3000, 0, id="warm_white"),
        pytest.param(4000, 118, id="mired_midpoint"),
        pytest.param(5000, 189, id="neutral"),
        pytest.param(6500, 255, id="cold_white"),
        pytest.param(2000, 0, id="below_range"),
        pytest.param(8000, 255, id="above_range"),
    ],
)
def test_kelvin_to_cct(kelvin: int, cct: int) -> None:
    """Test color temperatures map to the white mix in mireds, clamped."""
    assert kelvin_to_cct(kelvin, 3000, 6500) == cct


@pytest.mark.parametrize(
    ("cct", "kelvin"),
    [
        pytest.param(0, 3000, id="warm_white"),
        pytest.param(118, 3996, id="mired_midpoint"),
        pytest.param(255, 6500, id="cold_white"),
    ],
)
def test_cct_to_kelvin(cct: int, kelvin: int) -> None:
    """Test the white mix maps back to a color temperature."""
    assert cct_to_kelvin(cct, 3000, 6500) == kelvin

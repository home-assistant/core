"""Tests for Daikin Onecta utility helpers."""

import pytest

from homeassistant.components.daikin_onecta.utils import round_temperature_to_step


@pytest.mark.parametrize(
    ("value", "step", "minimum", "maximum", "expected"),
    [
        (40.3, None, None, None, 40.5),
        (80.0, None, None, None, 75.0),
        (9.0, 1.0, 10.0, 12.0, 10.0),
        (13.0, 1.0, 10.0, 12.0, 12.0),
    ],
)
def test_round_temperature_to_step_uses_defaults_and_bounds(
    value: float,
    step: float | None,
    minimum: float | None,
    maximum: float | None,
    expected: float,
) -> None:
    """Apply default step and fallback limits inside the shared helper."""
    assert (
        round_temperature_to_step(
            value,
            step,
            minimum,
            maximum,
            fallback_minimum=30.0,
            fallback_maximum=75.0,
        )
        == expected
    )

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
        pytest.param(
            70.0,
            0.5,
            43.3,
            60.0,
            59.8,
            id="native-maximum-aligns-down-to-step",
        ),
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


def test_round_temperature_to_step_uses_zero_when_minimum_is_missing() -> None:
    """Fallback limits clamp values without changing the native step origin."""
    assert (
        round_temperature_to_step(
            8.0,
            1.0,
            fallback_minimum=7.5,
            fallback_maximum=75.0,
        )
        == 8.0
    )


def test_round_temperature_to_step_aligns_fallback_minimum() -> None:
    """Clamp to the first supported step at or above an unaligned fallback."""
    assert (
        round_temperature_to_step(
            40.0,
            0.5,
            fallback_minimum=43.3,
            fallback_maximum=60.0,
        )
        == 43.5
    )


def test_round_temperature_to_step_uses_caller_default() -> None:
    """Allow water heaters to default to whole-degree temperature steps."""
    assert round_temperature_to_step(48.6, default_step=1) == 49

"""Test the Fan significant change platform."""

import pytest

from homeassistant.components.fan import FanEntityStateAttribute
from homeassistant.components.fan.significant_change import (
    async_check_significant_change,
)


async def test_significant_state_change() -> None:
    """Detect Fan significant state changes."""
    attrs = {}
    assert not async_check_significant_change(None, "on", attrs, "on", attrs)
    assert async_check_significant_change(None, "on", attrs, "off", attrs)


@pytest.mark.parametrize(
    ("old_attrs", "new_attrs", "expected_result"),
    [
        (
            {FanEntityStateAttribute.PERCENTAGE_STEP: "1"},
            {FanEntityStateAttribute.PERCENTAGE_STEP: "2"},
            False,
        ),
        (
            {FanEntityStateAttribute.PERCENTAGE: 1},
            {FanEntityStateAttribute.PERCENTAGE: 2},
            True,
        ),
        (
            {FanEntityStateAttribute.PERCENTAGE: 1},
            {FanEntityStateAttribute.PERCENTAGE: 1.9},
            False,
        ),
        (
            {FanEntityStateAttribute.PERCENTAGE: "invalid"},
            {FanEntityStateAttribute.PERCENTAGE: 1},
            True,
        ),
        (
            {FanEntityStateAttribute.PERCENTAGE: 1},
            {FanEntityStateAttribute.PERCENTAGE: "invalid"},
            False,
        ),
        (
            {FanEntityStateAttribute.DIRECTION: "front"},
            {FanEntityStateAttribute.DIRECTION: "front"},
            False,
        ),
        (
            {FanEntityStateAttribute.DIRECTION: "front"},
            {FanEntityStateAttribute.DIRECTION: "back"},
            True,
        ),
        (
            {FanEntityStateAttribute.OSCILLATING: True},
            {FanEntityStateAttribute.OSCILLATING: True},
            False,
        ),
        (
            {FanEntityStateAttribute.OSCILLATING: True},
            {FanEntityStateAttribute.OSCILLATING: False},
            True,
        ),
        (
            {FanEntityStateAttribute.PRESET_MODE: "auto"},
            {FanEntityStateAttribute.PRESET_MODE: "auto"},
            False,
        ),
        (
            {FanEntityStateAttribute.PRESET_MODE: "auto"},
            {FanEntityStateAttribute.PRESET_MODE: "whoosh"},
            True,
        ),
        (
            {
                FanEntityStateAttribute.PRESET_MODE: "auto",
                FanEntityStateAttribute.OSCILLATING: True,
            },
            {
                FanEntityStateAttribute.PRESET_MODE: "auto",
                FanEntityStateAttribute.OSCILLATING: False,
            },
            True,
        ),
    ],
)
async def test_significant_atributes_change(
    old_attrs: dict, new_attrs: dict, expected_result: bool
) -> None:
    """Detect Fan significant attribute changes."""
    assert (
        async_check_significant_change(None, "state", old_attrs, "state", new_attrs)
        == expected_result
    )

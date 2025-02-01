"""Test the Fan significant change platform."""

import pytest

from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PERCENTAGE_STEP,
    ATTR_PRESET_MODE,
)
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
        ({ATTR_PERCENTAGE_STEP: "1"}, {ATTR_PERCENTAGE_STEP: "2"}, False),
        ({ATTR_PERCENTAGE: 1}, {ATTR_PERCENTAGE: 2}, True),
        ({ATTR_PERCENTAGE: 1}, {ATTR_PERCENTAGE: 1.9}, False),
        ({ATTR_PERCENTAGE: "invalid"}, {ATTR_PERCENTAGE: 1}, True),
        ({ATTR_PERCENTAGE: 1}, {ATTR_PERCENTAGE: "invalid"}, False),
        ({ATTR_DIRECTION: "front"}, {ATTR_DIRECTION: "front"}, False),
        ({ATTR_DIRECTION: "front"}, {ATTR_DIRECTION: "back"}, True),
        ({ATTR_OSCILLATING: True}, {ATTR_OSCILLATING: True}, False),
        ({ATTR_OSCILLATING: True}, {ATTR_OSCILLATING: False}, True),
        ({ATTR_PRESET_MODE: "auto"}, {ATTR_PRESET_MODE: "auto"}, False),
        ({ATTR_PRESET_MODE: "auto"}, {ATTR_PRESET_MODE: "whoosh"}, True),
        (
            {ATTR_PRESET_MODE: "auto", ATTR_OSCILLATING: True},
            {ATTR_PRESET_MODE: "auto", ATTR_OSCILLATING: False},
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

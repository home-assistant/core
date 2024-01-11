"""Test the Vacuum significant change platform."""
import pytest

from homeassistant.components.vacuum import (
    ATTR_BATTERY_ICON,
    ATTR_BATTERY_LEVEL,
    ATTR_FAN_SPEED,
)
from homeassistant.components.vacuum.significant_change import (
    async_check_significant_change,
)


async def test_significant_state_change() -> None:
    """Detect Vacuum significant state changes."""
    attrs = {}
    assert not async_check_significant_change(None, "on", attrs, "on", attrs)
    assert async_check_significant_change(None, "on", attrs, "off", attrs)


@pytest.mark.parametrize(
    ("old_attrs", "new_attrs", "expected_result"),
    [
        ({ATTR_FAN_SPEED: "old_value"}, {ATTR_FAN_SPEED: "old_value"}, False),
        ({ATTR_FAN_SPEED: "old_value"}, {ATTR_FAN_SPEED: "new_value"}, True),
        # multiple attributes
        (
            {ATTR_FAN_SPEED: "old_value", ATTR_BATTERY_LEVEL: 10.0},
            {ATTR_FAN_SPEED: "new_value", ATTR_BATTERY_LEVEL: 10.0},
            True,
        ),
        # float attributes
        ({ATTR_BATTERY_LEVEL: 10.0}, {ATTR_BATTERY_LEVEL: 11.0}, True),
        ({ATTR_BATTERY_LEVEL: 10.0}, {ATTR_BATTERY_LEVEL: 10.9}, False),
        ({ATTR_BATTERY_LEVEL: "invalid"}, {ATTR_BATTERY_LEVEL: 10.0}, True),
        ({ATTR_BATTERY_LEVEL: 10.0}, {ATTR_BATTERY_LEVEL: "invalid"}, False),
        # insignificant attributes
        ({ATTR_BATTERY_ICON: "old_value"}, {ATTR_BATTERY_ICON: "new_value"}, False),
        ({ATTR_BATTERY_ICON: "old_value"}, {ATTR_BATTERY_ICON: "old_value"}, False),
        ({"unknown_attr": "old_value"}, {"unknown_attr": "old_value"}, False),
        ({"unknown_attr": "old_value"}, {"unknown_attr": "new_value"}, False),
    ],
)
async def test_significant_atributes_change(
    old_attrs: dict, new_attrs: dict, expected_result: bool
) -> None:
    """Detect Vacuum significant attribute changes."""
    assert (
        async_check_significant_change(None, "state", old_attrs, "state", new_attrs)
        == expected_result
    )

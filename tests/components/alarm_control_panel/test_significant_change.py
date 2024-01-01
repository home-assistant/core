"""Test the Alarm Control Panel significant change platform."""
import pytest

from homeassistant.components.alarm_control_panel import (
    ATTR_CHANGED_BY,
    ATTR_CODE_ARM_REQUIRED,
    ATTR_CODE_FORMAT,
)
from homeassistant.components.alarm_control_panel.significant_change import (
    async_check_significant_change,
)


async def test_significant_state_change() -> None:
    """Detect Alarm Control Panel significant state changes."""
    attrs = {}
    assert not async_check_significant_change(None, "on", attrs, "on", attrs)
    assert async_check_significant_change(None, "on", attrs, "off", attrs)


@pytest.mark.parametrize(
    ("old_attrs", "new_attrs", "expected_result"),
    [
        ({ATTR_CHANGED_BY: "old_value"}, {ATTR_CHANGED_BY: "old_value"}, False),
        ({ATTR_CHANGED_BY: "old_value"}, {ATTR_CHANGED_BY: "new_value"}, True),
        (
            {ATTR_CODE_ARM_REQUIRED: "old_value"},
            {ATTR_CODE_ARM_REQUIRED: "new_value"},
            True,
        ),
        # multiple attributes
        (
            {ATTR_CHANGED_BY: "old_value", ATTR_CODE_ARM_REQUIRED: "old_value"},
            {ATTR_CHANGED_BY: "new_value", ATTR_CODE_ARM_REQUIRED: "old_value"},
            True,
        ),
        # insignificant attributes
        ({ATTR_CODE_FORMAT: "old_value"}, {ATTR_CODE_FORMAT: "old_value"}, False),
        ({ATTR_CODE_FORMAT: "old_value"}, {ATTR_CODE_FORMAT: "new_value"}, False),
        ({"unknown_attr": "old_value"}, {"unknown_attr": "old_value"}, False),
        ({"unknown_attr": "old_value"}, {"unknown_attr": "new_value"}, False),
    ],
)
async def test_significant_atributes_change(
    old_attrs: dict, new_attrs: dict, expected_result: bool
) -> None:
    """Detect Humidifier significant attribute changes."""
    assert (
        async_check_significant_change(None, "state", old_attrs, "state", new_attrs)
        == expected_result
    )

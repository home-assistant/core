"""Test the Alarm Control Panel significant change platform."""

import pytest

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntityStateAttribute,
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
        (
            {AlarmControlPanelEntityStateAttribute.CHANGED_BY: "old_value"},
            {AlarmControlPanelEntityStateAttribute.CHANGED_BY: "old_value"},
            False,
        ),
        (
            {AlarmControlPanelEntityStateAttribute.CHANGED_BY: "old_value"},
            {AlarmControlPanelEntityStateAttribute.CHANGED_BY: "new_value"},
            True,
        ),
        (
            {AlarmControlPanelEntityStateAttribute.CODE_ARM_REQUIRED: "old_value"},
            {AlarmControlPanelEntityStateAttribute.CODE_ARM_REQUIRED: "new_value"},
            True,
        ),
        # multiple attributes
        (
            {
                AlarmControlPanelEntityStateAttribute.CHANGED_BY: "old_value",
                AlarmControlPanelEntityStateAttribute.CODE_ARM_REQUIRED: "old_value",
            },
            {
                AlarmControlPanelEntityStateAttribute.CHANGED_BY: "new_value",
                AlarmControlPanelEntityStateAttribute.CODE_ARM_REQUIRED: "old_value",
            },
            True,
        ),
        # insignificant attributes
        (
            {AlarmControlPanelEntityStateAttribute.CODE_FORMAT: "old_value"},
            {AlarmControlPanelEntityStateAttribute.CODE_FORMAT: "old_value"},
            False,
        ),
        (
            {AlarmControlPanelEntityStateAttribute.CODE_FORMAT: "old_value"},
            {AlarmControlPanelEntityStateAttribute.CODE_FORMAT: "new_value"},
            False,
        ),
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

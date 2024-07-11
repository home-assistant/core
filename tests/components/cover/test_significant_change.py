"""Test the Cover significant change platform."""

import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
)
from homeassistant.components.cover.significant_change import (
    async_check_significant_change,
)


async def test_significant_state_change() -> None:
    """Detect Cover significant state changes."""
    attrs = {}
    assert not async_check_significant_change(None, "on", attrs, "on", attrs)
    assert async_check_significant_change(None, "on", attrs, "off", attrs)


@pytest.mark.parametrize(
    ("old_attrs", "new_attrs", "expected_result"),
    [
        # float attributes
        ({ATTR_CURRENT_POSITION: 60.0}, {ATTR_CURRENT_POSITION: 61.0}, True),
        ({ATTR_CURRENT_POSITION: 60.0}, {ATTR_CURRENT_POSITION: 60.9}, False),
        ({ATTR_CURRENT_POSITION: "invalid"}, {ATTR_CURRENT_POSITION: 60.0}, True),
        ({ATTR_CURRENT_POSITION: 60.0}, {ATTR_CURRENT_POSITION: "invalid"}, False),
        ({ATTR_CURRENT_TILT_POSITION: 60.0}, {ATTR_CURRENT_TILT_POSITION: 61.0}, True),
        ({ATTR_CURRENT_TILT_POSITION: 60.0}, {ATTR_CURRENT_TILT_POSITION: 60.9}, False),
        # multiple attributes
        (
            {
                ATTR_CURRENT_POSITION: 60,
                ATTR_CURRENT_TILT_POSITION: 60,
            },
            {
                ATTR_CURRENT_POSITION: 60,
                ATTR_CURRENT_TILT_POSITION: 61,
            },
            True,
        ),
        (
            {
                ATTR_CURRENT_POSITION: 60,
                ATTR_CURRENT_TILT_POSITION: 59.1,
            },
            {
                ATTR_CURRENT_POSITION: 60,
                ATTR_CURRENT_TILT_POSITION: 60.9,
            },
            True,
        ),
        # insignificant attributes
        ({"unknown_attr": "old_value"}, {"unknown_attr": "old_value"}, False),
        ({"unknown_attr": "old_value"}, {"unknown_attr": "new_value"}, False),
    ],
)
async def test_significant_atributes_change(
    old_attrs: dict, new_attrs: dict, expected_result: bool
) -> None:
    """Detect Cover significant attribute changes."""
    assert (
        async_check_significant_change(None, "state", old_attrs, "state", new_attrs)
        == expected_result
    )

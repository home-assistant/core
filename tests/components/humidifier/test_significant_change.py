"""Test the Humidifier significant change platform."""
import pytest

from homeassistant.components.humidifier import (
    ATTR_ACTION,
    ATTR_CURRENT_HUMIDITY,
    ATTR_HUMIDITY,
    ATTR_MODE,
)
from homeassistant.components.humidifier.significant_change import (
    async_check_significant_change,
)


async def test_significant_state_change() -> None:
    """Detect Humidifier significant state changes."""
    attrs = {}
    assert not async_check_significant_change(None, "on", attrs, "on", attrs)
    assert async_check_significant_change(None, "on", attrs, "off", attrs)


@pytest.mark.parametrize(
    ("old_attrs", "new_attrs", "expected_result"),
    [
        ({ATTR_ACTION: "old_value"}, {ATTR_ACTION: "old_value"}, False),
        ({ATTR_ACTION: "old_value"}, {ATTR_ACTION: "new_value"}, True),
        ({ATTR_MODE: "old_value"}, {ATTR_MODE: "new_value"}, True),
        # multiple attributes
        (
            {ATTR_ACTION: "old_value", ATTR_MODE: "old_value"},
            {ATTR_ACTION: "new_value", ATTR_MODE: "old_value"},
            True,
        ),
        # float attributes
        ({ATTR_CURRENT_HUMIDITY: 60.0}, {ATTR_CURRENT_HUMIDITY: 61}, True),
        ({ATTR_CURRENT_HUMIDITY: 60.0}, {ATTR_CURRENT_HUMIDITY: 60.9}, False),
        ({ATTR_CURRENT_HUMIDITY: "invalid"}, {ATTR_CURRENT_HUMIDITY: 60.0}, True),
        ({ATTR_CURRENT_HUMIDITY: 60.0}, {ATTR_CURRENT_HUMIDITY: "invalid"}, False),
        ({ATTR_HUMIDITY: 62.0}, {ATTR_HUMIDITY: 63.0}, True),
        ({ATTR_HUMIDITY: 62.0}, {ATTR_HUMIDITY: 62.9}, False),
        # insignificant attributes
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

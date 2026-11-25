"""Test the Humidifier significant change platform."""

import pytest

from homeassistant.components.humidifier import HumidifierEntityStateAttribute
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
        (
            {HumidifierEntityStateAttribute.ACTION: "old_value"},
            {HumidifierEntityStateAttribute.ACTION: "old_value"},
            False,
        ),
        (
            {HumidifierEntityStateAttribute.ACTION: "old_value"},
            {HumidifierEntityStateAttribute.ACTION: "new_value"},
            True,
        ),
        (
            {HumidifierEntityStateAttribute.MODE: "old_value"},
            {HumidifierEntityStateAttribute.MODE: "new_value"},
            True,
        ),
        # multiple attributes
        (
            {
                HumidifierEntityStateAttribute.ACTION: "old_value",
                HumidifierEntityStateAttribute.MODE: "old_value",
            },
            {
                HumidifierEntityStateAttribute.ACTION: "new_value",
                HumidifierEntityStateAttribute.MODE: "old_value",
            },
            True,
        ),
        # float attributes
        (
            {HumidifierEntityStateAttribute.CURRENT_HUMIDITY: 60.0},
            {HumidifierEntityStateAttribute.CURRENT_HUMIDITY: 61},
            True,
        ),
        (
            {HumidifierEntityStateAttribute.CURRENT_HUMIDITY: 60.0},
            {HumidifierEntityStateAttribute.CURRENT_HUMIDITY: 60.9},
            False,
        ),
        (
            {HumidifierEntityStateAttribute.CURRENT_HUMIDITY: "invalid"},
            {HumidifierEntityStateAttribute.CURRENT_HUMIDITY: 60.0},
            True,
        ),
        (
            {HumidifierEntityStateAttribute.CURRENT_HUMIDITY: 60.0},
            {HumidifierEntityStateAttribute.CURRENT_HUMIDITY: "invalid"},
            False,
        ),
        (
            {HumidifierEntityStateAttribute.HUMIDITY: 62.0},
            {HumidifierEntityStateAttribute.HUMIDITY: 63.0},
            True,
        ),
        (
            {HumidifierEntityStateAttribute.HUMIDITY: 62.0},
            {HumidifierEntityStateAttribute.HUMIDITY: 62.9},
            False,
        ),
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

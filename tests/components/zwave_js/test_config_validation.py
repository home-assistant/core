"""Test the Z-Wave JS config validation helpers."""

from typing import Any

import pytest
import voluptuous as vol

from homeassistant.components.zwave_js.config_validation import VALUE_SCHEMA, boolean


@pytest.mark.parametrize(
    ("test_cases", "expected_value"),
    [
        ([True, "true", "yes", "on", "ON", "enable"], True),
        ([False, "false", "no", "off", "NO", "disable"], False),
        ([1.1, "1.1"], 1.1),
        ([1.0, "1.0"], 1.0),
        ([1, "1"], 1),
    ],
)
def test_validation(test_cases: list[Any], expected_value: Any) -> None:
    """Test config validation."""
    for case in test_cases:
        assert VALUE_SCHEMA(case) == expected_value


@pytest.mark.parametrize("value", ["invalid", "1", "0", 1, 0])
def test_invalid_boolean_validation(value: str | int) -> None:
    """Test invalid cases for boolean config validator."""
    with pytest.raises(vol.Invalid):
        boolean(value)

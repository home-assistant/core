"""Test validator integration."""
import voluptuous as vol

from homeassistant.components import validator
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_BATTERY_LEVEL,
    ATTR_FRIENDLY_NAME,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
)
from homeassistant.core import State


async def test_validate_base_attributes():
    """Test validating base attributes."""
    report = validator.Report()
    report.async_validate_base_attributes(
        State(
            "light.kitchen",
            "on",
            {
                ATTR_FRIENDLY_NAME: True,
                ATTR_SUPPORTED_FEATURES: "invalid mock type",
                ATTR_BATTERY_LEVEL: "invalid mock type",
                ATTR_ATTRIBUTION: True,
                ATTR_UNIT_OF_MEASUREMENT: True,
            },
        )
    )
    assert report.entities.get("light.kitchen", []) == [
        "Invalid value for friendly_name: not a valid value. Got True",
        "Invalid value for supported_features: not a valid value. Got 'invalid mock type'",
        "Invalid value for battery_level: not a valid value. Got 'invalid mock type'",
        "Invalid value for attribution: not a valid value. Got True",
        "Invalid value for unit_of_measurement: not a valid value. Got True",
    ]

    report = validator.Report()
    report.async_validate_base_attributes(State("light.kitchen", "on",))
    assert report.entities.get("light.kitchen", []) == []


async def test_validate_supported_features():
    """Test validating supported features."""
    report = validator.Report()
    support_feature_1 = 1
    support_feature_2 = 2
    support_feature_3 = 4
    supported_feature_validator = {
        support_feature_1: {},
        support_feature_2: {},
        support_feature_3: {
            "fan_mode": vol.Any("on", "off"),
            "fan_modes": vol.Schema([str]),
        },
    }

    report.async_validate_supported_features(
        State("light.kitchen", "on", {ATTR_SUPPORTED_FEATURES: 8}),
        supported_feature_validator,
    )
    assert report.entities.get("light.kitchen", []) == [
        "Unsupported feature flags found: 7",
    ]

    # report = validator.Report()
    # report.async_validate_base_attributes(State("light.kitchen", "on",))
    # assert report.entities.get("light.kitchen", []) == []

"""Test KNX DPT default attributes."""

import pytest

from homeassistant.components.knx.dpt import (
    _sensor_device_classes,
    _sensor_state_class_overrides,
)
from homeassistant.components.knx.schema import _sensor_attribute_sub_validator


@pytest.mark.parametrize(
    "dpt",
    {
        *_sensor_device_classes,
        *_sensor_state_class_overrides,
        "7",  # generic numeric DPT without specific device and state class
    },
)
def test_dpt_default_device_classes(dpt) -> None:
    """Test DPT default device and state classes and unit are valid."""
    assert _sensor_attribute_sub_validator(
        # YAML sensor config - only set type for this validation
        # other keys are not required for this test
        # UI validation works the same way, but uses different schema for config
        {"type": dpt}
    )

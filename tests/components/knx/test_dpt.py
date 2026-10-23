"""Test KNX DPT default attributes."""

import pytest
from xknx.dpt import DPTBase

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.knx.dpt import (
    _binary_sensor_device_classes,
    _sensor_device_classes,
    _sensor_state_class_overrides,
    _sensor_unit_overrides,
    get_binary_sensor_device_class,
)
from homeassistant.components.knx.schema import (
    _number_limit_sub_validator,
    _sensor_attribute_sub_validator,
)


@pytest.mark.parametrize(
    "dpt",
    sorted(
        {
            *_sensor_device_classes,
            *_sensor_state_class_overrides,
            *_sensor_unit_overrides,
            # add generic numeric DPTs without specific device and state class
            "7",
            "2byte_float",
        }
    ),
)
def test_dpt_default_device_classes(dpt: str) -> None:
    """Test DPT default device and state classes and unit are valid."""
    assert _sensor_attribute_sub_validator(
        # YAML sensor config - only set type for this validation
        # other keys are not required for this test
        # UI validation works the same way, but uses different schema for config
        {"type": dpt}
    )
    number_config = {"type": dpt}
    if dpt.startswith("14"):
        # DPT 14 has infinite range which isn't supported by HA
        # this test shall still check for correct device_class and unit_of_measurement
        number_config |= {"min": -500000, "max": 500000}
    assert _number_limit_sub_validator(number_config)


_BINARY_SENSOR_DEVICE_CLASSES = {
    "1.005": BinarySensorDeviceClass.PROBLEM,
    "1.010": BinarySensorDeviceClass.RUNNING,
    "1.011": BinarySensorDeviceClass.RUNNING,
    "1.018": BinarySensorDeviceClass.OCCUPANCY,
    "1.019": BinarySensorDeviceClass.OPENING,
}


@pytest.mark.parametrize(("dpt", "device_class"), _BINARY_SENSOR_DEVICE_CLASSES.items())
def test_binary_sensor_default_device_classes(
    dpt: str, device_class: BinarySensorDeviceClass
) -> None:
    """Test binary sensor default device classes by DPT 1 sub-type."""
    transcoder = DPTBase.parse_transcoder(dpt)
    assert transcoder is not None
    assert transcoder.dpt_main_number == 1
    assert get_binary_sensor_device_class(transcoder) is device_class


def test_binary_sensor_default_device_classes_complete() -> None:
    """Test no mapped DPT is missing from the explicit test cases."""
    assert _binary_sensor_device_classes.keys() == _BINARY_SENSOR_DEVICE_CLASSES.keys()

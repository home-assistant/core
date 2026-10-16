"""Tests for the sensor helpers."""

from collections.abc import Callable
import copy

import pytest
from sensor_state_data import SensorDeviceInfo

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info


def test_sensor_device_info_to_hass_device_info() -> None:
    """Test converting a sensor device info, which is cached by its values."""
    device_info = sensor_device_info_to_hass_device_info(
        SensorDeviceInfo(
            name="Thermometer",
            manufacturer="Acme",
            model="T1",
            sw_version=None,
            hw_version=None,
        )
    )
    assert device_info == DeviceInfo(
        name="Thermometer", manufacturer="Acme", model="T1"
    )

    # The same values give the same device info, so that comparing is cheap
    assert (
        sensor_device_info_to_hass_device_info(
            SensorDeviceInfo(
                name="Thermometer",
                manufacturer="Acme",
                model="T1",
                sw_version="1.0",
                hw_version=None,
            )
        )
        is device_info
    )

    # Values which are None are left unset
    assert sensor_device_info_to_hass_device_info(
        SensorDeviceInfo(
            name="Thermometer",
            manufacturer=None,
            model=None,
            sw_version=None,
            hw_version=None,
        )
    ).as_dict() == {"name": "Thermometer"}


def test_sensor_device_info_to_hass_device_info_read_only() -> None:
    """Test the shared device info cannot be modified, but can be copied."""
    device_info = sensor_device_info_to_hass_device_info(
        SensorDeviceInfo(
            name="Hygrometer",
            manufacturer="Acme",
            model="H1",
            sw_version=None,
            hw_version=None,
        )
    )

    with pytest.raises(TypeError, match="is shared and cannot be modified"):
        device_info["sw_version"] = "1.0"
    with pytest.raises(TypeError, match="is shared and cannot be modified"):
        device_info.sw_version = "1.0"
    with pytest.raises(TypeError, match="is shared and cannot be modified"):
        del device_info.model
    assert device_info.as_dict() == {
        "name": "Hygrometer",
        "manufacturer": "Acme",
        "model": "H1",
    }


@pytest.mark.parametrize(
    "copy_device_info",
    [
        pytest.param(lambda device_info: DeviceInfo(**device_info), id="unpack"),
        pytest.param(copy.copy, id="copy"),
        pytest.param(copy.deepcopy, id="deepcopy"),
    ],
)
def test_sensor_device_info_to_hass_device_info_copy(
    copy_device_info: Callable[[DeviceInfo], DeviceInfo],
) -> None:
    """Test a copy of the shared device info can be modified."""
    device_info = sensor_device_info_to_hass_device_info(
        SensorDeviceInfo(
            name="Barometer",
            manufacturer="Acme",
            model="B1",
            sw_version=None,
            hw_version=None,
        )
    )

    copied = copy_device_info(device_info)
    copied.sw_version = "1.0"
    assert copied.as_dict() == {
        "name": "Barometer",
        "manufacturer": "Acme",
        "model": "B1",
        "sw_version": "1.0",
    }
    assert "sw_version" not in device_info

"""Tests for the sensor helpers."""

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

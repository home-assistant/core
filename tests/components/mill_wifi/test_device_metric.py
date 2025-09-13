"""Tests for device metrics helpers."""

from custom_components.mill_wifi.device_capability import EDeviceCapability, EDeviceType
from custom_components.mill_wifi.device_metric import DeviceMetric


def test_get_power_state_heater():
    """Test getting power state for a typical heater."""
    device_data_on = {
        "isEnabled": True,
        "deviceType": {"childType": {"name": EDeviceType.PANEL_HEATER_GEN3.value}},
    }
    device_data_off = {
        "isEnabled": False,
        "deviceType": {"childType": {"name": EDeviceType.PANEL_HEATER_GEN3.value}},
    }
    assert DeviceMetric.get_power_state(device_data_on) is True
    assert DeviceMetric.get_power_state(device_data_off) is False


def test_get_power_state_heatpump():
    """Test getting power state for a heatpump."""
    device_data_on = {
        "deviceType": {"childType": {"name": EDeviceType.HEATPUMP.value}},
        "pumpAdditionalItems": {"state": {"pow": "on"}},
    }
    device_data_off = {
        "deviceType": {"childType": {"name": EDeviceType.HEATPUMP.value}},
        "pumpAdditionalItems": {"state": {"pow": "off"}},
    }
    assert DeviceMetric.get_power_state(device_data_on) is True
    assert DeviceMetric.get_power_state(device_data_off) is False


def test_get_target_temperature():
    """Test getting target temperature."""

    device_data = {"deviceSettings": {"reported": {"temperature_normal": 22.5}}}
    assert (
        DeviceMetric.get_capability_value(
            device_data, EDeviceCapability.TARGET_TEMPERATURE
        )
        == 22.5
    )

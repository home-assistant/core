"""Test VoIP devices."""

from __future__ import annotations

from voip_utils import CallInfo

from homeassistant.components.voip import DOMAIN, VoIPDevices
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceRegistry


async def test_device_registry_info(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    call_info: CallInfo,
    device_registry: DeviceRegistry,
) -> None:
    """Test info in device registry."""
    assert not voip_devices.async_allow_call(call_info)

    device = device_registry.async_get_device({(DOMAIN, call_info.caller_ip)})
    assert device is not None
    assert device.name == call_info.caller_ip
    assert device.manufacturer == "Grandstream"
    assert device.model == "HT801"
    assert device.sw_version == "1.0.17.5"

    # Test we update the device if the fw updates
    call_info.headers["user-agent"] = "Grandstream HT801 2.0.0.0"

    assert not voip_devices.async_allow_call(call_info)

    device = device_registry.async_get_device({(DOMAIN, call_info.caller_ip)})
    assert device.sw_version == "2.0.0.0"


async def test_device_registry_info_from_unknown_phone(
    hass: HomeAssistant,
    voip_devices: VoIPDevices,
    call_info: CallInfo,
    device_registry: DeviceRegistry,
) -> None:
    """Test info in device registry from unknown phone."""
    call_info.headers["user-agent"] = "Unknown"
    assert not voip_devices.async_allow_call(call_info)

    device = device_registry.async_get_device({(DOMAIN, call_info.caller_ip)})
    assert device.manufacturer is None
    assert device.model == "Unknown"
    assert device.sw_version is None

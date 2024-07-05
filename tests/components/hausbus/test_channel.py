"""Test the hausbus channel class."""

from pyhausbus.de.hausbus.homeassistant.proxy.controller.params.EFirmwareId import (
    EFirmwareId,
)
import pytest

from homeassistant.components.hausbus.device import HausbusDevice
from homeassistant.components.hausbus.entity import HausbusEntity


async def test_unique_id() -> None:
    """Test we create correct unique_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    channel = HausbusEntity("channel_type", 1, device)
    unique_id = channel.unique_id
    expected_unique_id = "device_id-channel_type1"
    assert unique_id == expected_unique_id


async def test_device_info() -> None:
    """Test we can access device info via channel."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    channel = HausbusEntity("channel_type", 1, device)
    device_info = channel.device_info
    assert device_info is not None
    assert device_info == device.device_info


async def test_translation_key() -> None:
    """Test of translation key."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    channel = HausbusEntity("channel_type", 1, device)
    translation_key = channel.translation_key
    expected_translation_key = "channel_type"
    assert translation_key == expected_translation_key


async def test_async_update_callback() -> None:
    """Test that generic channel does not provide update callback."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    channel = HausbusEntity("channel_type", 1, device)
    try:
        channel.async_update_callback()
    except NotImplementedError:
        pass
    else:
        pytest.fail(
            "Async Update Callback should not be implemented for this integration"
        )

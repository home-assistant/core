"""Test the hausbus device class."""

from pyhausbus.de.hausbus.homeassistant.proxy.controller.params.EFirmwareId import (
    EFirmwareId,
)

from homeassistant.components.hausbus.const import DOMAIN
from homeassistant.components.hausbus.device import HausbusDevice


async def test_device_id() -> None:
    """Test we can access device_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    assert device.device_id == "device_id"


async def test_device_info() -> None:
    """Test we can access device_info and it is filled according to the constructor."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device_info = device.device_info
    assert device_info is not None
    assert device_info.get("manufacturer") == "Haus-Bus.de"
    assert device_info.get("model") == "Controller"
    assert device_info.get("name") == "Controller ID device_id"
    assert device_info.get("sw_version") == "sw_version"
    assert device_info.get("hw_version") == "hw_version"
    assert device_info.get("identifiers") == {(DOMAIN, "device_id")}
    assert device_info.get("via_device") == (DOMAIN, "bridge_id")


async def test_missing_device_id() -> None:
    """Test device_info is None, if device_id is missing."""
    device = HausbusDevice(
        "bridge_id", None, "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device_info = device.device_info
    assert device_info is None


async def test_set_type_esp32_0x65() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device.set_type(0x65)
    assert device.model_id == "LAN-RS485 Brückenmodul"


async def test_set_type_esp32_0x18() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device.set_type(0x18)
    assert device.model_id == "6-fach Taster"


async def test_set_type_esp32_0x19() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device.set_type(0x19)
    assert device.model_id == "4-fach Taster"


async def test_set_type_esp32_0x1A() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device.set_type(0x1A)
    assert device.model_id == "2-fach Taster"


async def test_set_type_esp32_0x1B() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device.set_type(0x1B)
    assert device.model_id == "1-fach Taster"


async def test_set_type_esp32_0x1C() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device.set_type(0x1C)
    assert device.model_id == "6-fach Taster Gira"


async def test_set_type_esp32_0x20() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device.set_type(0x20)
    assert device.model_id == "32-fach IO"


async def test_set_type_esp32_0x0C() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device.set_type(0x0C)
    assert device.model_id == "16-fach Relais"


async def test_set_type_esp32_0x08() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device.set_type(0x08)
    assert device.model_id == "8-fach Relais"


async def test_set_type_esp32_0x10() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device.set_type(0x10)
    assert device.model_id == "22-fach UP-IO"


async def test_set_type_esp32_0x28() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device.set_type(0x28)
    assert device.model_id == "8-fach Dimmer"


async def test_set_type_esp32_0x30() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device.set_type(0x30)
    assert device.model_id == "2-fach RGB Dimmer"


async def test_set_type_esp32_0x00() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device.set_type(0x00)
    assert device.model_id == "4-fach 0-10V Dimmer"


async def test_set_type_esp32_0x01() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device.set_type(0x01)
    assert device.model_id == "4-fach 1-10V Dimmer"


async def test_set_type_hbc_0x18() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.HBC
    )
    device.set_type(0x18)
    assert device.model_id == "6-fach Taster"


async def test_set_type_hbc_0x19() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.HBC
    )
    device.set_type(0x19)
    assert device.model_id == "4-fach Taster"


async def test_set_type_hbc_0x1A() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.HBC
    )
    device.set_type(0x1A)
    assert device.model_id == "2-fach Taster"


async def test_set_type_hbc_0x1B() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.HBC
    )
    device.set_type(0x1B)
    assert device.model_id == "1-fach Taster"


async def test_set_type_hbc_0x1C() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.HBC
    )
    device.set_type(0x1C)
    assert device.model_id == "6-fach Taster Gira"


async def test_set_type_hbc_0x20() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.HBC
    )
    device.set_type(0x20)
    assert device.model_id == "32-fach IO"


async def test_set_type_hbc_0x0C() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.HBC
    )
    device.set_type(0x0C)
    assert device.model_id == "16-fach Relais"


async def test_set_type_hbc_0x08() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.HBC
    )
    device.set_type(0x08)
    assert device.model_id == "8-fach Relais"


async def test_set_type_hbc_0x10() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.HBC
    )
    device.set_type(0x10)
    assert device.model_id == "24-fach UP-IO"


async def test_set_type_hbc_0x28() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.HBC
    )
    device.set_type(0x28)
    assert device.model_id == "8-fach Dimmer"


async def test_set_type_hbc_0x29() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.HBC
    )
    device.set_type(0x29)
    assert device.model_id == "8-fach Dimmer"


async def test_set_type_hbc_0x30() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.HBC
    )
    device.set_type(0x30)
    assert device.model_id == "2-fach RGB Dimmer"


async def test_set_type_hbc_0x00() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.HBC
    )
    device.set_type(0x00)
    assert device.model_id == "4-fach 0-10V Dimmer"


async def test_set_type_hbc_0x01() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.HBC
    )
    device.set_type(0x01)
    assert device.model_id == "4-fach 1-10V Dimmer"


async def test_set_type_sd485_0x28() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.SD485
    )
    device.set_type(0x28)
    assert device.model_id == "24-fach UP-IO"


async def test_set_type_sd485_0x1E() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.SD485
    )
    device.set_type(0x1E)
    assert device.model_id == "6-fach Taster"


async def test_set_type_sd485_0x2E() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.SD485
    )
    device.set_type(0x2E)
    assert device.model_id == "6-fach Taster"


async def test_set_type_sd485_0x2F() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.SD485
    )
    device.set_type(0x2F)
    assert device.model_id == "6-fach Taster"


async def test_set_type_sd485_0x2B() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.SD485
    )
    device.set_type(0x2B)
    assert device.model_id == "4-fach 0-10V Dimmer"


async def test_set_type_sd485_0x2C() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.SD485
    )
    device.set_type(0x2C)
    assert device.model_id == "4-fach Taster"


async def test_set_type_sd485_0x2D() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.SD485
    )
    device.set_type(0x2D)
    assert device.model_id == "4-fach 1-10V Dimmer"


async def test_set_type_sd485_0x2A() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.SD485
    )
    device.set_type(0x2A)
    assert device.model_id == "2-fach Taster"


async def test_set_type_sd485_0x29() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.SD485
    )
    device.set_type(0x29)
    assert device.model_id == "1-fach Taster"


async def test_set_type_ar8_0x28() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.AR8
    )
    device.set_type(0x28)
    assert device.model_id == "LAN Brückenmodul"


async def test_set_type_ar8_0x30() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.AR8
    )
    device.set_type(0x30)
    assert device.model_id == "8-fach Relais"


async def test_set_type_sd6_0x14() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.SD6
    )
    device.set_type(0x14)
    assert device.model_id == "Multitaster"


async def test_set_type_sd6_0x1E() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.SD6
    )
    device.set_type(0x1E)
    assert device.model_id == "Multitaster"


async def test_set_type_esp32_default() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.ESP32
    )
    device.set_type(0x99)  # An unsupported type
    assert device.model_id == "Controller"


async def test_set_type_hbc_default() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.HBC
    )
    device.set_type(0x99)  # An unsupported type
    assert device.model_id == "Controller"


async def test_set_type_sd485_default() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.SD485
    )
    device.set_type(0x99)  # An unsupported type
    assert device.model_id == "Controller"


async def test_set_type_ar8_default() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.AR8
    )
    device.set_type(0x99)  # An unsupported type
    assert device.model_id == "Controller"


async def test_set_type_sd6_default() -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice(
        "bridge_id", "device_id", "sw_version", "hw_version", EFirmwareId.SD6
    )
    device.set_type(0x99)  # An unsupported type
    assert device.model_id == "Controller"

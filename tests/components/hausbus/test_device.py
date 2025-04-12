"""Test the hausbus device class."""

from pyhausbus.de.hausbus.homeassistant.proxy.controller.params.EFirmwareId import (
    EFirmwareId,
)
import pytest

from homeassistant.components.hausbus.const import DOMAIN
from homeassistant.components.hausbus.device import HausbusDevice


async def test_device_id() -> None:
    """Test we can access device_id."""
    device = HausbusDevice("device_id", "sw_version", "hw_version", EFirmwareId.ESP32)
    assert device.device_id == "device_id"


async def test_device_info() -> None:
    """Test we can access device_info and it is filled according to the constructor."""
    device = HausbusDevice("device_id", "sw_version", "hw_version", EFirmwareId.ESP32)
    device_info = device.device_info
    assert device_info is not None
    assert device_info.get("manufacturer") == "Haus-Bus.de"
    assert device_info.get("model") == "Controller"
    assert device_info.get("name") == "Controller device_id"
    assert device_info.get("sw_version") == "sw_version"
    assert device_info.get("hw_version") == "hw_version"
    assert device_info.get("identifiers") == {(DOMAIN, "device_id")}


@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        (
            {"firmware": EFirmwareId.ESP32, "type": 0x65},
            {"model_id": "LAN-RS485 Brückenmodul"},
        ),
        ({"firmware": EFirmwareId.ESP32, "type": 0x18}, {"model_id": "6-fach Taster"}),
        ({"firmware": EFirmwareId.ESP32, "type": 0x19}, {"model_id": "4-fach Taster"}),
        ({"firmware": EFirmwareId.ESP32, "type": 0x1A}, {"model_id": "2-fach Taster"}),
        ({"firmware": EFirmwareId.ESP32, "type": 0x1B}, {"model_id": "1-fach Taster"}),
        (
            {"firmware": EFirmwareId.ESP32, "type": 0x1C},
            {"model_id": "6-fach Taster Gira"},
        ),
        ({"firmware": EFirmwareId.ESP32, "type": 0x20}, {"model_id": "32-fach IO"}),
        ({"firmware": EFirmwareId.ESP32, "type": 0x0C}, {"model_id": "16-fach Relais"}),
        ({"firmware": EFirmwareId.ESP32, "type": 0x08}, {"model_id": "8-fach Relais"}),
        ({"firmware": EFirmwareId.ESP32, "type": 0x10}, {"model_id": "22-fach UP-IO"}),
        ({"firmware": EFirmwareId.ESP32, "type": 0x28}, {"model_id": "8-fach Dimmer"}),
        (
            {"firmware": EFirmwareId.ESP32, "type": 0x30},
            {"model_id": "2-fach RGB Dimmer"},
        ),
        (
            {"firmware": EFirmwareId.ESP32, "type": 0x00},
            {"model_id": "4-fach 0-10V Dimmer"},
        ),
        (
            {"firmware": EFirmwareId.ESP32, "type": 0x01},
            {"model_id": "4-fach 1-10V Dimmer"},
        ),
        ({"firmware": EFirmwareId.ESP32, "type": 0x99}, {"model_id": "Controller"}),
        ({"firmware": EFirmwareId.HBC, "type": 0x18}, {"model_id": "6-fach Taster"}),
        ({"firmware": EFirmwareId.HBC, "type": 0x19}, {"model_id": "4-fach Taster"}),
        ({"firmware": EFirmwareId.HBC, "type": 0x1A}, {"model_id": "2-fach Taster"}),
        ({"firmware": EFirmwareId.HBC, "type": 0x1B}, {"model_id": "1-fach Taster"}),
        (
            {"firmware": EFirmwareId.HBC, "type": 0x1C},
            {"model_id": "6-fach Taster Gira"},
        ),
        ({"firmware": EFirmwareId.HBC, "type": 0x20}, {"model_id": "32-fach IO"}),
        ({"firmware": EFirmwareId.HBC, "type": 0x0C}, {"model_id": "16-fach Relais"}),
        ({"firmware": EFirmwareId.HBC, "type": 0x08}, {"model_id": "8-fach Relais"}),
        ({"firmware": EFirmwareId.HBC, "type": 0x10}, {"model_id": "24-fach UP-IO"}),
        ({"firmware": EFirmwareId.HBC, "type": 0x28}, {"model_id": "8-fach Dimmer"}),
        ({"firmware": EFirmwareId.HBC, "type": 0x29}, {"model_id": "8-fach Dimmer"}),
        (
            {"firmware": EFirmwareId.HBC, "type": 0x30},
            {"model_id": "2-fach RGB Dimmer"},
        ),
        (
            {"firmware": EFirmwareId.HBC, "type": 0x00},
            {"model_id": "4-fach 0-10V Dimmer"},
        ),
        (
            {"firmware": EFirmwareId.HBC, "type": 0x01},
            {"model_id": "4-fach 1-10V Dimmer"},
        ),
        ({"firmware": EFirmwareId.HBC, "type": 0x99}, {"model_id": "Controller"}),
        ({"firmware": EFirmwareId.SD485, "type": 0x28}, {"model_id": "24-fach UP-IO"}),
        ({"firmware": EFirmwareId.SD485, "type": 0x1E}, {"model_id": "6-fach Taster"}),
        ({"firmware": EFirmwareId.SD485, "type": 0x2E}, {"model_id": "6-fach Taster"}),
        ({"firmware": EFirmwareId.SD485, "type": 0x2F}, {"model_id": "6-fach Taster"}),
        (
            {"firmware": EFirmwareId.SD485, "type": 0x2B},
            {"model_id": "4-fach 0-10V Dimmer"},
        ),
        ({"firmware": EFirmwareId.SD485, "type": 0x2C}, {"model_id": "4-fach Taster"}),
        (
            {"firmware": EFirmwareId.SD485, "type": 0x2D},
            {"model_id": "4-fach 1-10V Dimmer"},
        ),
        ({"firmware": EFirmwareId.SD485, "type": 0x2A}, {"model_id": "2-fach Taster"}),
        ({"firmware": EFirmwareId.SD485, "type": 0x29}, {"model_id": "1-fach Taster"}),
        ({"firmware": EFirmwareId.SD485, "type": 0x99}, {"model_id": "Controller"}),
        ({"firmware": EFirmwareId.AR8, "type": 0x28}, {"model_id": "LAN Brückenmodul"}),
        ({"firmware": EFirmwareId.AR8, "type": 0x30}, {"model_id": "8-fach Relais"}),
        ({"firmware": EFirmwareId.AR8, "type": 0x99}, {"model_id": "Controller"}),
        ({"firmware": EFirmwareId.SD6, "type": 0x14}, {"model_id": "Multitaster"}),
        ({"firmware": EFirmwareId.SD6, "type": 0x1E}, {"model_id": "Multitaster"}),
        ({"firmware": EFirmwareId.SD6, "type": 0x99}, {"model_id": "Controller"}),
        (
            {"firmware": EFirmwareId.SER_UNKNOWN, "type": 0x99},
            {"model_id": "Controller"},
        ),
    ],
)
async def test_set_type(inputs, expected) -> None:
    """Test setting the type adjusts the model_id."""
    device = HausbusDevice("device_id", "sw_version", "hw_version", inputs["firmware"])
    device.set_type(inputs["type"])
    assert device.model_id == expected["model_id"]

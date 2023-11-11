"""Test the hausbus light class."""


from pyhausbus.de.hausbus.homeassistant.proxy.controller.params.EFirmwareId import (
    EFirmwareId,
)
from pyhausbus.de.hausbus.homeassistant.proxy.Dimmer import Dimmer
from pyhausbus.de.hausbus.homeassistant.proxy.Led import Led
from pyhausbus.de.hausbus.homeassistant.proxy.RGBDimmer import RGBDimmer
from pyhausbus.ObjectId import ObjectId
import pytest

from homeassistant.components.hausbus.device import HausbusDevice
from homeassistant.components.hausbus.light import HausbusLight
from homeassistant.components.light import ColorMode
from homeassistant.core import HomeAssistant


async def test_create_dimmer(hass: HomeAssistant) -> None:
    """Test creating a Dimmer channel."""

    device = HausbusDevice("1", "1", "0", "0", EFirmwareId.ESP32)
    instance = Dimmer.create(1, 1)
    object_id = ObjectId(instance.getObjectId())  # = 0x00 01 17 01
    light = HausbusLight(
        object_id.getInstanceId(),
        device,
        instance,
    )

    # Assert that the color mode is set according to the light type
    assert ColorMode.BRIGHTNESS in light._attr_supported_color_modes


async def test_create_led(hass: HomeAssistant) -> None:
    """Test creating a LED channel."""

    device = HausbusDevice("1", "1", "0", "0", EFirmwareId.ESP32)
    instance = Led.create(1, 1)
    object_id = ObjectId(instance.getObjectId())  # = 0x00 01 17 01
    light = HausbusLight(
        object_id.getInstanceId(),
        device,
        instance,
    )

    # Assert that the color mode is set according to the light type
    assert ColorMode.BRIGHTNESS in light._attr_supported_color_modes


async def test_create_rgbdimmer(hass: HomeAssistant) -> None:
    """Test creating a RGB Dimmer channel."""

    device = HausbusDevice("1", "1", "0", "0", EFirmwareId.ESP32)
    instance = RGBDimmer.create(1, 1)
    object_id = ObjectId(instance.getObjectId())  # = 0x00 01 17 01
    light = HausbusLight(
        object_id.getInstanceId(),
        device,
        instance,
    )

    # Assert that the color mode is set according to the light type
    assert ColorMode.HS in light._attr_supported_color_modes


@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        (Dimmer.CLASS_ID, True),
        (Led.CLASS_ID, True),
        (RGBDimmer.CLASS_ID, True),
        (0, False),
    ],
)
async def test_is_light_channel(inputs, expected) -> None:
    """Test return value of is_light_channel."""

    # Assert that the color mode is set according to the light type
    assert HausbusLight.is_light_channel(inputs) == expected

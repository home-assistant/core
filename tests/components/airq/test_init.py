"""Test the air-Q integration init."""

from unittest.mock import AsyncMock

from homeassistant.components.airq.const import DOMAIN, MANUFACTURER
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_platform
from .common import TEST_DEVICE_INFO


async def test_device_info(
    hass: HomeAssistant,
    mock_airq: AsyncMock,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that the device is registered with correct info after setup."""
    await setup_platform(hass, Platform.SENSOR)

    device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_DEVICE_INFO["id"])}
    )
    assert device is not None
    assert device.manufacturer == MANUFACTURER
    assert device.name == TEST_DEVICE_INFO["name"]
    assert device.model == TEST_DEVICE_INFO["model"]
    assert device.sw_version == TEST_DEVICE_INFO["sw_version"]
    assert device.hw_version == TEST_DEVICE_INFO["hw_version"]
    assert device.serial_number == TEST_DEVICE_INFO["id"]

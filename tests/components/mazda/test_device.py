"""The device tests for the Mazda Connected Services integration."""

from homeassistant.components.mazda.const import DOMAIN
from homeassistant.helpers import device_registry as dr

from tests.components.mazda import init_integration


async def test_device_nickname(hass):
    """Test creation of the device when vehicle has a nickname."""
    await init_integration(hass, use_nickname=True)

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "JM000000000000000")},
    )

    assert reg_device.model == "2021 MAZDA3 2.5 S SE AWD"
    assert reg_device.manufacturer == "Mazda"
    assert reg_device.name == "My Mazda3"


async def test_device_no_nickname(hass):
    """Test creation of the device when vehicle has no nickname."""
    await init_integration(hass, use_nickname=False)

    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "JM000000000000000")},
    )

    assert reg_device.model == "2021 MAZDA3 2.5 S SE AWD"
    assert reg_device.manufacturer == "Mazda"
    assert reg_device.name == "2021 MAZDA3 2.5 S SE AWD"

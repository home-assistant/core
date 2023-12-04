"""Tests for the device created by the A. O. Smith integration."""

from homeassistant.components.aosmith.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry


async def test_device_nickname(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test creation of the device."""
    device_registry = dr.async_get(hass)
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, "junctionId")},
    )

    assert reg_device.manufacturer == "A. O. Smith"
    assert reg_device.name == "My water heater"
    assert reg_device.model == "HPTS-50 200 202172000"
    assert reg_device.serial_number == "serial"
    assert reg_device.suggested_area == "Basement"
    assert reg_device.sw_version == "2.14"

"""Tests for Hydrawise devices."""

from unittest.mock import Mock

from homeassistant.components.hydrawise.const import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr


def test_zones_in_device_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_added_config_entry: ConfigEntry,
    mock_pydrawise: Mock,
) -> None:
    """Test that devices are added to the device registry."""

    device1 = device_registry.async_get_device(identifiers={(DOMAIN, "5965394")})
    assert device1 is not None
    assert device1.name == "Zone One"
    assert device1.manufacturer == "Hydrawise"

    device2 = device_registry.async_get_device(identifiers={(DOMAIN, "5965395")})
    assert device2 is not None
    assert device2.name == "Zone Two"
    assert device2.manufacturer == "Hydrawise"


def test_controller_in_device_registry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_added_config_entry: ConfigEntry,
    mock_pydrawise: Mock,
) -> None:
    """Test that devices are added to the device registry."""
    device = device_registry.async_get_device(identifiers={(DOMAIN, "52496")})
    assert device is not None
    assert device.name == "Home Controller"
    assert device.manufacturer == "Hydrawise"

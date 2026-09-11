"""Tests for Hydrawise devices."""

from unittest.mock import Mock

import pytest

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

    device1 = device_registry.async_get_device_by_identifier(
        (DOMAIN, "5965394"), mock_added_config_entry.entry_id
    )
    assert device1 is not None
    assert device1.name == "Zone One"
    assert device1.manufacturer == "Hydrawise"

    device2 = device_registry.async_get_device_by_identifier(
        (DOMAIN, "5965395"), mock_added_config_entry.entry_id
    )
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
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, "52496"), mock_added_config_entry.entry_id
    )
    assert device is not None
    assert device.name == "Home Controller"
    assert device.manufacturer == "Hydrawise"


@pytest.mark.usefixtures("mock_pydrawise")
def test_zone_via_device_links_to_controller(
    device_registry: dr.DeviceRegistry,
    mock_added_config_entry: ConfigEntry,
) -> None:
    """Test that a zone device links to its controller via via_device_id."""
    controller = device_registry.async_get_device_by_identifier(
        (DOMAIN, "52496"), mock_added_config_entry.entry_id
    )
    assert controller is not None

    zone = device_registry.async_get_device_by_identifier(
        (DOMAIN, "5965394"), mock_added_config_entry.entry_id
    )
    assert zone is not None
    assert zone.via_device_id == controller.id


@pytest.mark.usefixtures("mock_pydrawise")
def test_controller_has_no_self_via_device(
    device_registry: dr.DeviceRegistry,
    mock_added_config_entry: ConfigEntry,
) -> None:
    """Test the controller device does not link to itself via via_device_id.

    Sensor entities share the controller device, so they must not set
    via_device_id, which would point the controller device at itself.
    """
    controller = device_registry.async_get_device_by_identifier(
        (DOMAIN, "52496"), mock_added_config_entry.entry_id
    )
    assert controller is not None
    assert controller.via_device_id is None

"""Tests for the Daikin BR entity."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.daikin_br.const import DOMAIN
from homeassistant.components.daikin_br.entity import DaikinEntity


# pylint: disable=redefined-outer-name, too-few-public-methods
# pylint: disable=protected-access
@pytest.fixture
def dummy_coordinator():
    """Create a dummy coordinator for testing purposes."""
    coordinator = MagicMock()
    # Minimal dummy data; it is not used by the entity logic here.
    coordinator.data = {"port1": {"fw_ver": "1.0.0"}}
    coordinator.hass = MagicMock()
    return coordinator


def test_attr_has_entity_name(dummy_coordinator) -> None:
    """Test that _attr_has_entity_name is True."""
    entity = DaikinEntity(dummy_coordinator)
    assert entity._attr_has_entity_name is True


def test_device_info_property(dummy_coordinator) -> None:
    """Test that device_info returns the correct DeviceInfo data."""
    entity = DaikinEntity(dummy_coordinator)
    # Manually assign required attributes.
    entity._unique_id = "test_unique_id"
    entity._device_name = "Test Device"
    entity._device_info = {"fw_ver": "1.2.3"}

    # Retrieve the device info.
    info = entity.device_info

    # Expected values
    expected_identifiers = {(DOMAIN, "test_unique_id")}
    expected_name = "Test Device"
    expected_manufacturer = "Daikin"
    expected_model = "Smart AC Series"
    expected_sw_version = "1.2.3"

    # Assert each key of the device_info dictionary.
    assert info["identifiers"] == expected_identifiers
    assert info["name"] == expected_name
    assert info["manufacturer"] == expected_manufacturer
    assert info["model"] == expected_model
    assert info["sw_version"] == expected_sw_version

"""Test TuneBlade base entity behavior."""

from unittest.mock import Mock

import pytest

from homeassistant.components.tuneblade_remote.const import DOMAIN, NAME
from homeassistant.components.tuneblade_remote.entity import TuneBladeEntity
from homeassistant.helpers.device_registry import DeviceInfo


@pytest.fixture
def mock_coordinator() -> Mock:
    """Mock coordinator for TuneBlade entities."""
    return Mock()


@pytest.fixture
def mock_config_entry() -> Mock:
    """Mock config entry for TuneBlade entities."""
    entry = Mock()
    entry.entry_id = "test_entry_id"
    return entry


def test_entity_init_defaults(mock_coordinator: Mock, mock_config_entry: Mock) -> None:
    """Test TuneBladeEntity initialization with default device_id and device_name."""
    entity = TuneBladeEntity(mock_coordinator, mock_config_entry)

    assert entity.device_id == "master"
    assert entity.device_name == "Master"
    assert entity._attr_unique_id == "test_entry_id_master"
    assert isinstance(entity._attr_device_info, DeviceInfo)
    assert (DOMAIN, "master") in entity._attr_device_info.identifiers
    assert entity._attr_device_info.name == f"Master {NAME}"
    assert entity._attr_device_info.manufacturer == NAME


def test_entity_init_custom(mock_coordinator: Mock, mock_config_entry: Mock) -> None:
    """Test TuneBladeEntity initialization with custom device_id and device_name."""
    entity = TuneBladeEntity(
        mock_coordinator,
        mock_config_entry,
        device_id="device123",
        device_name="Living Room",
    )

    assert entity.device_id == "device123"
    assert entity.device_name == "Living Room"
    assert entity._attr_unique_id == "test_entry_id_device123"
    assert isinstance(entity._attr_device_info, DeviceInfo)
    assert (DOMAIN, "device123") in entity._attr_device_info.identifiers
    assert entity._attr_device_info.name == f"Living Room {NAME}"
    assert entity._attr_device_info.manufacturer == NAME

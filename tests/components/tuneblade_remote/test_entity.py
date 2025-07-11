"""Test TuneBlade base entity behavior."""

import pytest

from homeassistant.components.tuneblade_remote.const import DOMAIN, NAME
from homeassistant.components.tuneblade_remote.entity import TuneBladeEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from tests.common import MockConfigEntry


@pytest.fixture
def mock_coordinator(hass: HomeAssistant) -> DataUpdateCoordinator:
    """Return a mock coordinator for TuneBlade entities."""
    coordinator = DataUpdateCoordinator(hass, _logger=None, name=DOMAIN)
    coordinator.data = {}
    return coordinator


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry for TuneBlade entities."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="TuneBlade",
        data={"host": "localhost", "port": 54412, "name": "TuneBlade"},
        unique_id="test_entry_id",
    )


def test_entity_init_defaults(
    mock_coordinator: DataUpdateCoordinator, mock_config_entry: MockConfigEntry
) -> None:
    """Test TuneBladeEntity initialization with default device_id and device_name."""
    entity = TuneBladeEntity(mock_coordinator, mock_config_entry)

    assert entity.device_id == "master"
    assert entity.device_name == "Master"
    assert entity.unique_id == "test_entry_id_master"
    assert isinstance(entity.device_info, DeviceInfo)
    assert entity.device_info.identifiers == {(DOMAIN, "master")}
    assert entity.device_info.name == f"Master {NAME}"
    assert entity.device_info.manufacturer == NAME


def test_entity_init_custom(
    mock_coordinator: DataUpdateCoordinator, mock_config_entry: MockConfigEntry
) -> None:
    """Test TuneBladeEntity initialization with custom device_id and device_name."""
    entity = TuneBladeEntity(
        mock_coordinator,
        mock_config_entry,
        device_id="device123",
        device_name="Living Room",
    )

    assert entity.device_id == "device123"
    assert entity.device_name == "Living Room"
    assert entity.unique_id == "test_entry_id_device123"
    assert isinstance(entity.device_info, DeviceInfo)
    assert entity.device_info.identifiers == {(DOMAIN, "device123")}
    assert entity.device_info.name == f"Living Room {NAME}"
    assert entity.device_info.manufacturer == NAME

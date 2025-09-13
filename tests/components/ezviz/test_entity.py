"""Test the EZVIZ entity base classes."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.ezviz.const import DOMAIN, MANUFACTURER
from homeassistant.components.ezviz.entity import EzvizBaseEntity, EzvizEntity
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@pytest.fixture
def mock_coordinator():
    """Mock the EZVIZ coordinator."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.data = {
        "C666666": {
            "name": "Test Camera",
            "mac_address": "aa:bb:cc:dd:ee:ff",
            "device_sub_category": "CS-C6N-A0-1D2WFR",
            "version": "5.3.0",
            "status": 1,
            "battery_level": 85,
        }
    }
    return coordinator


async def test_ezviz_entity_initialization(mock_coordinator: MagicMock) -> None:
    """Test EzvizEntity initialization."""
    entity = EzvizEntity(mock_coordinator, "C666666")

    assert entity._serial == "C666666"
    assert entity._camera_name == "Test Camera"
    assert entity._attr_has_entity_name is True


async def test_ezviz_entity_data_property(mock_coordinator: MagicMock) -> None:
    """Test EzvizEntity data property."""
    entity = EzvizEntity(mock_coordinator, "C666666")

    data = entity.data
    assert data["name"] == "Test Camera"
    assert data["mac_address"] == "aa:bb:cc:dd:ee:ff"
    assert data["device_sub_category"] == "CS-C6N-A0-1D2WFR"
    assert data["version"] == "5.3.0"
    assert data["status"] == 1
    assert data["battery_level"] == 85


async def test_ezviz_entity_availability(mock_coordinator: MagicMock) -> None:
    """Test EzvizEntity availability property."""
    entity = EzvizEntity(mock_coordinator, "C666666")

    # Test with available camera (status != 2)
    assert entity.available is True

    # Test with unavailable camera (status == 2)
    mock_coordinator.data["C666666"]["status"] = 2
    assert entity.available is False


async def test_ezviz_entity_device_info(mock_coordinator: MagicMock) -> None:
    """Test EzvizEntity device info."""
    entity = EzvizEntity(mock_coordinator, "C666666")

    device_info = entity.device_info
    assert device_info["identifiers"] == {(DOMAIN, "C666666")}
    assert device_info["connections"] == {(CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")}
    assert device_info["manufacturer"] == MANUFACTURER
    assert device_info["model"] == "CS-C6N-A0-1D2WFR"
    assert device_info["name"] == "Test Camera"
    assert device_info["sw_version"] == "5.3.0"


async def test_ezviz_base_entity_initialization(mock_coordinator: MagicMock) -> None:
    """Test EzvizBaseEntity initialization."""
    entity = EzvizBaseEntity(mock_coordinator, "C666666")

    assert entity._serial == "C666666"
    assert entity._camera_name == "Test Camera"
    assert entity._attr_has_entity_name is True
    assert entity.coordinator == mock_coordinator


async def test_ezviz_base_entity_data_property(mock_coordinator: MagicMock) -> None:
    """Test EzvizBaseEntity data property."""
    entity = EzvizBaseEntity(mock_coordinator, "C666666")

    data = entity.data
    assert data["name"] == "Test Camera"
    assert data["mac_address"] == "aa:bb:cc:dd:ee:ff"
    assert data["device_sub_category"] == "CS-C6N-A0-1D2WFR"
    assert data["version"] == "5.3.0"
    assert data["status"] == 1
    assert data["battery_level"] == 85


async def test_ezviz_base_entity_availability(mock_coordinator: MagicMock) -> None:
    """Test EzvizBaseEntity availability property."""
    entity = EzvizBaseEntity(mock_coordinator, "C666666")

    # Test with available camera (status != 2)
    assert entity.available is True

    # Test with unavailable camera (status == 2)
    mock_coordinator.data["C666666"]["status"] = 2
    assert entity.available is False


async def test_ezviz_base_entity_device_info(mock_coordinator: MagicMock) -> None:
    """Test EzvizBaseEntity device info."""
    entity = EzvizBaseEntity(mock_coordinator, "C666666")

    device_info = entity.device_info
    assert device_info["identifiers"] == {(DOMAIN, "C666666")}
    assert device_info["connections"] == {(CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")}
    assert device_info["manufacturer"] == MANUFACTURER
    assert device_info["model"] == "CS-C6N-A0-1D2WFR"
    assert device_info["name"] == "Test Camera"
    assert device_info["sw_version"] == "5.3.0"


async def test_entity_with_missing_data_fields(mock_coordinator: MagicMock) -> None:
    """Test entity behavior with missing data fields."""
    # Create coordinator with minimal data
    minimal_coordinator = MagicMock(spec=DataUpdateCoordinator)
    minimal_coordinator.data = {
        "C666666": {
            "name": "Minimal Camera",
            "mac_address": "aa:bb:cc:dd:ee:ff",
            "device_sub_category": "Unknown",
            "version": "1.0.0",
            "status": 1,
        }
    }

    entity = EzvizEntity(minimal_coordinator, "C666666")

    assert entity._camera_name == "Minimal Camera"
    assert entity.available is True

    device_info = entity.device_info
    assert device_info["name"] == "Minimal Camera"
    assert device_info["model"] == "Unknown"
    assert device_info["sw_version"] == "1.0.0"


async def test_entity_coordinator_inheritance(mock_coordinator: MagicMock) -> None:
    """Test that EzvizEntity properly inherits from CoordinatorEntity."""
    entity = EzvizEntity(mock_coordinator, "C666666")

    # Should have coordinator property from CoordinatorEntity
    assert entity.coordinator == mock_coordinator

    # Should have entity name attribute
    assert entity._attr_has_entity_name is True


async def test_entity_base_coordinator_assignment(mock_coordinator: MagicMock) -> None:
    """Test that EzvizBaseEntity properly assigns coordinator."""
    entity = EzvizBaseEntity(mock_coordinator, "C666666")

    # Should have coordinator property assigned
    assert entity.coordinator == mock_coordinator

    # Should have entity name attribute
    assert entity._attr_has_entity_name is True


async def test_entity_status_edge_cases(mock_coordinator: MagicMock) -> None:
    """Test entity availability with different status values."""
    entity = EzvizEntity(mock_coordinator, "C666666")

    # Test various status values
    test_cases = [
        (0, True),  # Status 0 should be available
        (1, True),  # Status 1 should be available
        (2, False),  # Status 2 should be unavailable
        (3, True),  # Status 3 should be available
        (-1, True),  # Negative status should be available
    ]

    for status, expected_available in test_cases:
        mock_coordinator.data["C666666"]["status"] = status
        assert entity.available == expected_available, (
            f"Status {status} should be {'available' if expected_available else 'unavailable'}"
        )


async def test_entity_device_info_connections_format(
    mock_coordinator: MagicMock,
) -> None:
    """Test that device info connections are properly formatted."""
    entity = EzvizEntity(mock_coordinator, "C666666")

    device_info = entity.device_info
    connections = device_info["connections"]

    # Should have exactly one connection
    assert len(connections) == 1

    # Should be a set of tuples
    connection = list(connections)[0]
    assert isinstance(connection, tuple)
    assert len(connection) == 2
    assert connection[0] == CONNECTION_NETWORK_MAC
    assert connection[1] == "aa:bb:cc:dd:ee:ff"


async def test_entity_device_info_identifiers_format(
    mock_coordinator: MagicMock,
) -> None:
    """Test that device info identifiers are properly formatted."""
    entity = EzvizEntity(mock_coordinator, "C666666")

    device_info = entity.device_info
    identifiers = device_info["identifiers"]

    # Should have exactly one identifier
    assert len(identifiers) == 1

    # Should be a set of tuples
    identifier = list(identifiers)[0]
    assert isinstance(identifier, tuple)
    assert len(identifier) == 2
    assert identifier[0] == DOMAIN
    assert identifier[1] == "C666666"

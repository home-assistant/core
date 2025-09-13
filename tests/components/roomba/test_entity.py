"""Tests for iRobotEntity properties in the Roomba integration."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from roombapy import Roomba

from homeassistant.components.roomba.entity import IRobotEntity


@pytest.fixture
def mock_roomba_state() -> dict[str, Any]:
    """Fixture to provide a mock Roomba state."""
    return {
        "tankLvl": 42,
        "dock": {"tankLvl": 99},
        "hwPartsRev": {"navSerialNo": "12345", "wlan0HwAddr": "AA:BB:CC:DD:EE:FF"},
        "sku": "980",
        "name": "Test Roomba",
        "softwareVer": "3.2.1",
        "hardwareRev": "1.0",
    }


@pytest.fixture
def mock_roomba(mock_roomba_state: dict[str, Any]) -> Roomba:
    """Fixture to create a mock Roomba instance."""
    roomba = MagicMock()
    roomba.master_state = {"state": {"reported": mock_roomba_state}}
    return roomba


class DummyEntity(IRobotEntity):
    """Dummy Roomba entity for testing purposes."""

    def on_message(self, json_data: dict[str, Any]) -> None:
        """Handle incoming messages."""


def test_tank_level_property(mock_roomba: Roomba) -> None:
    """Test the tank level property of the IRobotEntity."""
    entity = DummyEntity(mock_roomba, "blid123")
    assert entity.tank_level == 42


def test_dock_tank_level_property(mock_roomba: Roomba) -> None:
    """Test the dock tank level property of the IRobotEntity."""
    entity = DummyEntity(mock_roomba, "blid123")
    assert entity.dock_tank_level == 99


def test_tank_level_none() -> None:
    """Test tank_level property returns None if not present."""
    mock_state = {
        "dock": {"tankLvl": 99},
        "hwPartsRev": {"navSerialNo": "12345", "wlan0HwAddr": "AA:BB:CC:DD:EE:FF"},
        "sku": "980",
        "name": "Test Roomba",
        "softwareVer": "3.2.1",
        "hardwareRev": "1.0",
    }
    roomba = MagicMock()
    roomba.master_state = {"state": {"reported": mock_state}}
    entity = DummyEntity(roomba, "blid123")
    assert entity.tank_level is None


def test_dock_tank_level_none() -> None:
    """Test dock_tank_level property returns None if not present."""
    mock_state = {
        "tankLvl": 42,
        "dock": {},
        "hwPartsRev": {"navSerialNo": "12345", "wlan0HwAddr": "AA:BB:CC:DD:EE:FF"},
        "sku": "980",
        "name": "Test Roomba",
        "softwareVer": "3.2.1",
        "hardwareRev": "1.0",
    }
    roomba = MagicMock()
    roomba.master_state = {"state": {"reported": mock_state}}
    entity = DummyEntity(roomba, "blid123")
    assert entity.dock_tank_level is None

"""Tests for IRobotEntity usage in Roomba vacuum platform."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from roombapy import Roomba

from homeassistant.components.roomba.vacuum import IRobotVacuum


@pytest.fixture
def mock_roomba_state() -> dict[str, Any]:
    """Fixture to provide a mock Roomba state."""
    return {
        "cap": {"pose": 1},
        "cleanMissionStatus": {"cycle": "none", "phase": "charge"},
        "softwareVer": "3.2.1",
        "pose": {"point": {"x": 1, "y": 2}, "theta": 90},
        "hwPartsRev": {"navSerialNo": "12345", "wlan0HwAddr": "AA:BB:CC:DD:EE:FF"},
        "sku": "980",
        "name": "Test Roomba",
        "hardwareRev": "1.0",
        "bin": {"present": True, "full": False},
    }


@pytest.fixture
def mock_roomba(mock_roomba_state: dict[str, Any]) -> Roomba:
    """Fixture to create a mock Roomba vacuum instance."""
    roomba = MagicMock()
    roomba.send_command = MagicMock()
    roomba.error_code = 0
    roomba.error_message = None
    roomba.current_state = "run"
    roomba.set_preference = MagicMock()
    roomba.register_on_message_callback = MagicMock()
    roomba.master_state = {"state": {"reported": mock_roomba_state}}
    return roomba


class DummyVacuumEntity(IRobotVacuum):
    """Dummy Roomba vacuum entity for testing purposes."""

    def on_message(self, json_data: dict[str, Any]) -> None:
        """Handle incoming messages."""


def test_ir_robot_vacuum_properties(mock_roomba: Roomba) -> None:
    """Test properties of IRobotVacuum entity."""
    entity = DummyVacuumEntity(mock_roomba, "blid123")
    # Check activity property
    assert entity.activity is not None
    # Check extra_state_attributes includes expected keys
    attrs = entity.extra_state_attributes
    assert "software_version" in attrs
    assert "status" in attrs
    assert "position" in attrs

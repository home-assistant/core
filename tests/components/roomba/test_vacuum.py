"""Tests for IRobotEntity usage in Roomba vacuum platform."""

from collections.abc import Iterable
from typing import Any
from unittest.mock import MagicMock

import pytest
from roombapy import Roomba

from homeassistant.components.roomba.models import RoombaData
from homeassistant.components.roomba.vacuum import (
    BraavaJet,
    IRobotVacuum,
    RoombaVacuum,
    RoombaVacuumCarpetBoost,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity


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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "expected_class", "expected_extra_attrs"),
    [
        (
            {"cap": {}, "bin": {"present": True, "full": False}, "detectedPad": True},
            BraavaJet,
            8,
        ),
        ({"cap": {"carpetBoost": 1}}, RoombaVacuumCarpetBoost, 2),
        ({"cap": {"carpetBoost": 0}}, RoombaVacuum, 2),
        ({"cap": {}}, RoombaVacuum, 2),
    ],
)
async def test_async_setup_entry_selects_correct_class(
    mock_roomba: Roomba,
    state: dict[str, Any],
    expected_class: type[IRobotVacuum],
    expected_extra_attrs: int,
) -> None:
    """Test async_setup_entry selects the correct vacuum class based on state."""
    # Setup mocks
    hass = MagicMock(spec=HomeAssistant)
    config_entry = MagicMock(spec=ConfigEntry)
    config_entry.entry_id = "test_entry"
    master_state = {"state": {"reported": state}}
    mock_roomba.master_state.update(master_state)
    blid = "blid123"
    hass.data = {"roomba": {"test_entry": RoombaData(roomba=mock_roomba, blid=blid)}}

    added_entities: list[Entity] = []

    def async_add_entities(
        new_entities: Iterable[Entity],
        update_before_add: bool = False,
        *,
        config_subentry_id: str | None = None,
    ) -> None:
        added_entities.extend(list(new_entities))

    await async_setup_entry(hass, config_entry, async_add_entities)
    assert len(added_entities) == 1

    assert isinstance(added_entities[0], expected_class)
    assert len(added_entities[0].extra_state_attributes) == expected_extra_attrs

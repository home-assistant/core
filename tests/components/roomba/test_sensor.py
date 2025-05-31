"""Tests for IRobotEntity usage in Roomba sensor platform."""

from collections.abc import Iterable
from typing import Any
from unittest.mock import MagicMock

import pytest
from roombapy import Roomba

from homeassistant.components.roomba.models import RoombaData
from homeassistant.components.roomba.sensor import async_setup_entry
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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("state", "expected_sensors"),
    [
        (
            {},
            12,
        ),
        ({"dock": {}}, 12),
        ({"dock": {"tankLvl": 10}}, 13),
    ],
)
async def test_async_setup_entry_selects_correct_class(
    mock_roomba: Roomba,
    state: dict[str, Any],
    expected_sensors: int,
) -> None:
    """Test async_setup_entry selects the correct amount of sensors based on state."""
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
    assert len(added_entities) == expected_sensors

"""Fixtures for Intergas InComfort integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.incomfort.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_heater_status() -> dict[str, Any]:
    """Mock heater status."""
    return {
        "display_code": 126,
        "display_text": "standby",
        "fault_code": None,
        "is_burning": False,
        "is_failed": False,
        "is_pumping": False,
        "is_tapping": False,
        "heater_temp": 35.34,
        "tap_temp": 30.21,
        "pressure": 1.86,
        "serial_no": "2404c08648",
        "nodenr": 249,
        "rf_message_rssi": 30,
        "rfstatus_cntr": 0,
    }


@pytest.fixture
def mock_room_status() -> dict[str, Any]:
    """Mock room status."""
    return {"room_temp": 21.42, "setpoint": 18.0, "override": 18.0}


@pytest.fixture
def mock_incomfort(
    hass: HomeAssistant,
    mock_heater_status: dict[str, Any],
    mock_room_status: dict[str, Any],
) -> Generator[MagicMock, None]:
    """Mock the InComfort gateway client."""

    class MockRoom:
        """Mocked InComfort room class."""

        override: float
        room_no: int
        room_temp: float
        setpoint: float
        status: dict[str, Any]

        def __init__(self) -> None:
            """Initialize mocked room."""
            self.override = mock_room_status["override"]
            self.room_no = 1
            self.room_temp = mock_room_status["room_temp"]
            self.setpoint = mock_room_status["setpoint"]
            self.status = mock_room_status

    class MockHeater:
        """Mocked InComfort heater class."""

        serial_no: str
        status: dict[str, Any]
        rooms: list[MockRoom]

        def __init__(self) -> None:
            """Initialize mocked heater."""
            self.serial_no = "c0ffeec0ffee"

        async def update(self) -> None:
            self.status = mock_heater_status
            self.rooms = [MockRoom]

    with patch(
        "homeassistant.components.incomfort.models.InComfortGateway", MagicMock()
    ) as patch_gateway:
        patch_gateway().heaters = AsyncMock()
        patch_gateway().heaters.return_value = [MockHeater()]
        yield patch_gateway

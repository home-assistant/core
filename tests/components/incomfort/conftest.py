"""Fixtures for Intergas InComfort integration."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from incomfortclient import DisplayCode
import pytest

from homeassistant.components.incomfort.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_CONFIG = {
    "host": "192.168.1.12",
    "username": "admin",
    "password": "verysecret",
}

MOCK_CONFIG_DHCP = {
    "username": "admin",
    "password": "verysecret",
}

MOCK_HEATER_STATUS = {
    "display_code": DisplayCode.STANDBY,
    "display_text": "standby",
    "fault_code": None,
    "is_burning": False,
    "is_failed": False,
    "is_pumping": False,
    "is_tapping": False,
    "heater_temp": 35.34,
    "tap_temp": 30.21,
    "pressure": 1.86,
    "serial_no": "c0ffeec0ffee",
    "nodenr": 249,
    "rf_message_rssi": 30,
    "rfstatus_cntr": 0,
}

MOCK_HEATER_STATUS_HEATING = {
    "display_code": DisplayCode.OPENTHERM,
    "display_text": "opentherm",
    "fault_code": None,
    "is_burning": True,
    "is_failed": False,
    "is_pumping": True,
    "is_tapping": False,
    "heater_temp": 35.34,
    "tap_temp": 30.21,
    "pressure": 1.86,
    "serial_no": "c0ffeec0ffee",
    "nodenr": 249,
    "rf_message_rssi": 30,
    "rfstatus_cntr": 0,
}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.incomfort.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_entry_data() -> dict[str, Any]:
    """Mock config entry data for fixture."""
    return MOCK_CONFIG


@pytest.fixture
def mock_entry_options() -> dict[str, Any] | None:
    """Mock config entry options for fixture."""
    return None


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant,
    mock_entry_data: dict[str, Any],
    mock_entry_options: dict[str, Any],
) -> MockConfigEntry:
    """Mock a config entry setup for incomfort integration."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=mock_entry_data, options=mock_entry_options
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_heater_status() -> dict[str, Any]:
    """Mock heater status."""
    return dict(MOCK_HEATER_STATUS)


@pytest.fixture
def mock_room_status() -> dict[str, Any]:
    """Mock room status."""
    return {"room_temp": 21.42, "setpoint": 18.0, "override": 18.0}


@pytest.fixture
def mock_incomfort(
    mock_heater_status: dict[str, Any],
    mock_room_status: dict[str, Any],
) -> Generator[MagicMock]:
    """Mock the InComfort gateway client."""

    class MockRoom:
        """Mocked InComfort room class."""

        override: float
        room_no: int
        room_temp: float
        setpoint: float
        status: dict[str, Any]
        set_override: MagicMock

        def __init__(self) -> None:
            """Initialize mocked room."""
            self.room_no = 1
            self.status = mock_room_status
            self.set_override = MagicMock()

        @property
        def override(self) -> str:
            return mock_room_status["override"]

        @property
        def room_temp(self) -> float:
            return mock_room_status["room_temp"]

        @property
        def setpoint(self) -> float:
            return mock_room_status["setpoint"]

    class MockHeater:
        """Mocked InComfort heater class."""

        serial_no: str
        status: dict[str, Any]
        rooms: list[MockRoom]
        is_failed: bool
        is_pumping: bool
        display_code: int
        display_text: str | None
        fault_code: int | None
        is_burning: bool
        is_tapping: bool
        heater_temp: float
        tap_temp: float
        pressure: float
        serial_no: str
        nodenr: int
        rf_message_rssi: int
        rfstatus_cntr: int

        def __init__(self) -> None:
            """Initialize mocked heater."""
            self.serial_no = "c0ffeec0ffee"

        async def update(self) -> None:
            self.status = mock_heater_status
            for key, value in mock_heater_status.items():
                setattr(self, key, value)
            self.rooms = [MockRoom()]

    with patch(
        "homeassistant.components.incomfort.coordinator.InComfortGateway", MagicMock()
    ) as patch_gateway:
        patch_gateway().heaters = AsyncMock()
        patch_gateway().heaters.return_value = [MockHeater()]
        patch_gateway().mock_heater_status = mock_heater_status
        patch_gateway().mock_room_status = mock_room_status
        yield patch_gateway

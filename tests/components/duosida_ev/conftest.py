"""Fixtures for Duosida EV integration tests."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.duosida_ev.const import (
    CONF_DEVICE_ID,
    DEFAULT_PORT,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


# Mock data - realistic charger status
MOCK_CHARGER_STATUS = {
    "conn_status": 2,  # Charging
    "cp_voltage": 6.0,  # 6V = charging
    "voltage": 230.0,  # L1 voltage
    "voltage_l2": 230.0,
    "voltage_l3": 230.0,
    "current": 16.0,  # 16A charging current
    "current_l2": 16.0,
    "current_l3": 16.0,
    "power": 11040,  # 3 * 230V * 16A
    "temperature_station": 35.0,  # 35°C - charger station temperature
    "session_energy": 5.5,  # 5.5 kWh this session
    "session_time": 120,  # 120 minutes = 2 hours
    "model": "SmartChargePI",
    "manufacturer": "Duosida",
    "firmware": "1.0.0",
}

# Mock configuration entry data
MOCK_CONFIG_ENTRY_DATA = {
    CONF_HOST: "192.168.1.100",
    CONF_PORT: DEFAULT_PORT,
    CONF_DEVICE_ID: "03123456789012345678",
}

# Mock discovered charger
MOCK_DISCOVERED_CHARGER = {
    "ip": "192.168.1.100",
    "port": 9988,
    "device_id": "03123456789012345678",
    "model": "SmartChargePI",
}


class MockChargerStatus:
    """Mock charger status object that supports to_dict()."""

    def __init__(self, status_dict: dict[str, Any]) -> None:
        """Initialize with status data."""
        self._status = status_dict

    def to_dict(self) -> dict[str, Any]:
        """Return status as dictionary."""
        return self._status


class MockDuosidaCharger:
    """Mock DuosidaCharger for testing."""

    def __init__(
        self, host: str, port: int = 9988, device_id: str = "", debug: bool = False
    ) -> None:
        """Initialize mock charger."""
        self.host = host
        self.port = port
        self.device_id = device_id
        self.debug = debug
        self._connected = False
        self._status = MOCK_CHARGER_STATUS.copy()

    def connect(self) -> bool:
        """Mock connect."""
        self._connected = True
        return True

    def disconnect(self) -> None:
        """Mock disconnect."""
        self._connected = False

    def get_status(self) -> MockChargerStatus:
        """Mock get_status - returns object with to_dict() method."""
        if not self._connected:
            raise ConnectionError("Not connected")
        return MockChargerStatus(self._status)

    def start_charging(self) -> bool:
        """Mock start_charging."""
        if not self._connected:
            return False
        self._status["conn_status"] = 2  # Charging
        return True

    def stop_charging(self) -> bool:
        """Mock stop_charging."""
        if not self._connected:
            return False
        self._status["conn_status"] = 0  # Available
        return True

    def set_max_current(self, current: int) -> bool:
        """Mock set_max_current."""
        if not self._connected:
            return False
        if not 6 <= current <= 32:
            return False
        self._status["current"] = float(current)
        return True

    def set_led_brightness(self, brightness: int) -> bool:
        """Mock set_led_brightness."""
        if not self._connected:
            return False
        if brightness not in (0, 1, 3):
            return False
        return True

    def set_direct_work_mode(self, enabled: bool) -> bool:
        """Mock set_direct_work_mode."""
        return self._connected

    def set_stop_on_disconnect(self, enabled: bool) -> bool:
        """Mock set_stop_on_disconnect."""
        return self._connected

    def set_max_voltage(self, voltage: int) -> bool:
        """Mock set_max_voltage."""
        if not self._connected:
            return False
        return 265 <= voltage <= 290

    def set_min_voltage(self, voltage: int) -> bool:
        """Mock set_min_voltage."""
        if not self._connected:
            return False
        return 70 <= voltage <= 110


@pytest.fixture
def mock_charger() -> MockDuosidaCharger:
    """Return a mock charger instance."""
    return MockDuosidaCharger(
        host="192.168.1.100",
        port=9988,
        device_id="03123456789012345678",
    )


@pytest.fixture
def mock_duosida_charger() -> Generator[MagicMock]:
    """Mock the DuosidaCharger class."""
    mock_charger_instance = MockDuosidaCharger(
        host="192.168.1.100",
        port=9988,
        device_id="03123456789012345678",
    )
    with (
        patch(
            "homeassistant.components.duosida_ev.DuosidaCharger",
            return_value=mock_charger_instance,
        ) as mock,
        patch(
            "homeassistant.components.duosida_ev.coordinator.DuosidaCharger",
            return_value=mock_charger_instance,
        ),
        patch(
            "homeassistant.components.duosida_ev.config_flow.DuosidaCharger",
            return_value=mock_charger_instance,
        ),
    ):
        yield mock


@pytest.fixture
def mock_discover_chargers() -> Generator[MagicMock]:
    """Mock discover_chargers function."""
    with patch(
        "homeassistant.components.duosida_ev.config_flow.discover_chargers",
        return_value=[MOCK_DISCOVERED_CHARGER],
    ) as mock:
        yield mock


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry."""
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        title="Duosida EV Charger",
        data=MOCK_CONFIG_ENTRY_DATA,
        source="user",
        entry_id="test_entry_id",
        unique_id="03123456789012345678",
    )
    entry.add_to_hass(hass)
    return entry


async def _setup_integration(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> None:
    """Set up the Duosida EV integration."""
    with (
        patch(
            "homeassistant.components.duosida_ev.coordinator.Store.async_load",
            return_value=None,
        ),
        patch(
            "homeassistant.components.duosida_ev.coordinator.Store.async_save",
            return_value=None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duosida_charger: MagicMock,
) -> None:
    """Set up the Duosida EV integration for tests."""
    await _setup_integration(hass, mock_config_entry)

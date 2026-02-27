"""Shared test fixtures for Diesel Heater tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create a mock Home Assistant instance for config flow tests."""
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []
    hass.config_entries.flow.async_progress_by_handler.return_value = []
    return hass


@pytest.fixture
def mock_coordinator() -> MagicMock:
    """Create a mock VevorHeaterCoordinator."""
    coordinator = MagicMock()
    coordinator._address = "AA:BB:CC:DD:EE:FF"
    coordinator.address = "AA:BB:CC:DD:EE:FF"
    coordinator._heater_id = "EE:FF"
    coordinator.last_update_success = True
    coordinator.send_command = AsyncMock(return_value=True)
    coordinator.async_set_temperature = AsyncMock()
    coordinator.async_turn_on = AsyncMock()
    coordinator.async_turn_off = AsyncMock()
    coordinator.data = {
        "connected": True,
        "running_state": 1,
        "running_step": 3,
        "running_mode": 2,
        "set_level": 5,
        "set_temp": 22,
        "cab_temperature": 20.5,
        "case_temperature": 50,
        "supply_voltage": 12.5,
        "error_code": 0,
    }
    return coordinator


@pytest.fixture
def mock_config_entry() -> MagicMock:
    """Create a mock config entry."""
    entry = MagicMock()
    entry.data = {
        "address": "AA:BB:CC:DD:EE:FF",
        "preset_away_temp": 8,
        "preset_comfort_temp": 21,
    }
    entry.options = {}
    entry.entry_id = "test_entry"
    return entry

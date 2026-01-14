"""Fixtures for NRGkick integration tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.nrgkick.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nrgkick.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_nrgkick_api():
    """Mock NRGkickAPI."""
    with patch(
        "homeassistant.components.nrgkick.api.NRGkickAPI", autospec=True
    ) as mock_api:
        api = mock_api.return_value
        api.test_connection = AsyncMock(return_value=True)
        api.get_info = AsyncMock(
            return_value={
                "general": {
                    "device_name": "NRGkick Test",
                    "serial_number": "TEST123456",
                    "rated_current": 32.0,
                }
            }
        )
        api.get_control = AsyncMock(
            return_value={
                "current_set": 16.0,
                "charge_pause": 0,
                "energy_limit": 0,
                "phase_count": 3,
            }
        )
        api.get_values = AsyncMock(
            return_value={
                "powerflow": {
                    "power": {"total": 11000},
                    "current": {"total": 16.0},
                    "voltage": {"total": 230.0},
                },
                "energy": {"charged_energy": 5000},
                "status": {"charging_status": 3},
            }
        )
        # Mock set methods to return actual API responses (with the new value)
        api.set_current = AsyncMock(return_value={"current_set": 16.0})
        api.set_charge_pause = AsyncMock(return_value={"charge_pause": 0})
        api.set_energy_limit = AsyncMock(return_value={"energy_limit": 0})
        api.set_phase_count = AsyncMock(return_value={"phase_count": 3})
        yield api


@pytest.fixture
def mock_config_entry():
    """Mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="NRGkick Test",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_pass",
        },
        entry_id="test_entry_id",
        unique_id="TEST123456",
    )


@pytest.fixture
def mock_info_data():
    """Mock device info data."""
    return {
        "general": {
            "device_name": "NRGkick Test",
            "serial_number": "TEST123456",
            "model_type": "Gen2",
            "rated_current": 32.0,
            "json_api_version": "v1",
        },
        "connector": {
            "type": "TYPE2",
            "serial_number": "CONN123",
            "max_current": 32.0,
            "phase_count": 3,
        },
        "grid": {
            "voltage": 230,
            "frequency": 50.0,
            "phases": "L1, L2, L3",
        },
        "network": {
            "ip_address": "192.168.1.100",
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "wifi_ssid": "TestNetwork",
            "wifi_rssi": -45,
        },
        "hardware": {
            "smartmodule_version": "4.0.0.0",
            "bluetooth_version": "1.2.3",
        },
        "software": {
            "firmware_version": "2.1.0",
        },
    }


@pytest.fixture
def mock_control_data():
    """Mock control data."""
    return {
        "current_set": 16.0,
        "charge_pause": 0,
        "energy_limit": 0,
        "phase_count": 3,
    }


@pytest.fixture
def mock_values_data():
    """Mock values data."""
    return {
        "powerflow": {
            "power": {"total": 11000, "l1": 3666, "l2": 3667, "l3": 3667},
            "current": {"total": 16.0, "l1": 5.33, "l2": 5.33, "l3": 5.34},
            "voltage": {"total": 230.0, "l1": 230.0, "l2": 230.0, "l3": 230.0},
            "frequency": 50.0,
            "power_factor": 0.98,
        },
        "energy": {
            "charged_energy": 5000,
            "session_energy": 2500,
        },
        "status": {
            "charging_status": 3,
            "charge_permitted": True,
        },
        "temperatures": {
            "housing": 35.0,
            "connector_l1": 28.0,
            "connector_l2": 29.0,
            "connector_l3": 28.5,
        },
    }

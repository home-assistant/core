"""Configuration for Saunum Leil integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.saunum.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        title="Saunum Leil Sauna",
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 502,
        },
        unique_id="192.168.1.100:502",
    )


@pytest.fixture
def mock_modbus_client() -> Generator[MagicMock]:
    """Return a mocked Modbus client for config flow tests."""
    with patch(
        "homeassistant.components.saunum.config_flow.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        # Mock holding registers response for successful connection test
        mock_response = MagicMock()
        mock_response.isError.return_value = False
        mock_response.registers = [0, 80, 60, 10, 2, 0, 0]  # Valid control parameters

        mock_client.read_holding_registers = AsyncMock(return_value=mock_response)

        yield mock_client


@pytest.fixture
def mock_modbus_coordinator() -> Generator[MagicMock]:
    """Return a mocked Modbus client for coordinator tests."""
    with patch(
        "homeassistant.components.saunum.AsyncModbusTcpClient"
    ) as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connected = True
        mock_client.connect = AsyncMock(return_value=True)
        mock_client.close = MagicMock()

        # Mock holding registers (control parameters)
        mock_holding_response = MagicMock()
        mock_holding_response.isError.return_value = False
        mock_holding_response.registers = [
            0,
            80,
            60,
            10,
            2,
            0,
            0,
        ]  # Sample control data

        # Mock sensor registers (sensor data from holding registers)
        mock_sensor_response = MagicMock()
        mock_sensor_response.isError.return_value = False
        mock_sensor_response.registers = [75, 1234, 5678, 3, 0]  # Sample sensor data

        # Mock alarm registers (default to no alarms)
        mock_alarm_response = MagicMock()
        mock_alarm_response.isError.return_value = False
        mock_alarm_response.registers = [0, 0, 0, 0, 0, 0]  # No alarms

        def mock_read_holding_registers(address, count, device_id=1):
            """Mock read_holding_registers with different responses based on address."""
            if address == 0:  # Control data
                return mock_holding_response
            if address == 100:  # Sensor data
                return mock_sensor_response
            if address == 200:  # Alarm data
                return mock_alarm_response
            return mock_holding_response

        mock_client.read_holding_registers = AsyncMock(
            side_effect=mock_read_holding_registers
        )
        mock_client.write_register = AsyncMock(return_value=mock_holding_response)

        yield mock_client


@pytest.fixture
def mock_setup_platforms():
    """Mock async_forward_entry_setups."""
    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"
    ) as mock_setup:
        mock_setup.return_value = True
        yield mock_setup

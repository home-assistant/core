"""Fixtures for the Intesis Modbus integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from modbus_connection.mock import MockModbusConnection
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.intesis_modbus.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_ENTRY_DATA, seed_single_unit


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.intesis_modbus.async_setup_entry",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_connection() -> MockModbusConnection:
    """A fake Modbus connection seeded as a healthy MHI single-unit gateway."""
    connection = MockModbusConnection()
    seed_single_unit(connection.for_unit(1))
    return connection


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a single-unit gateway config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTESTINTESISSINGLE000000",
        unique_id="/dev/ttyUSB0:1",
        data=MOCK_ENTRY_DATA,
        title="INMBSMHI001R000",
    )


@pytest.fixture
def mock_get_unit(mock_connection: MockModbusConnection) -> Generator[MagicMock]:
    """Hand out units on the mock connection when the entry sets up."""
    with patch(
        "homeassistant.components.intesis_modbus.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ) as mock_get_unit:
        yield mock_get_unit


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> MockConfigEntry:
    """Set up the Intesis Modbus integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return mock_config_entry

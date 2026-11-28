"""Fixtures for the Zehnder ComfoConnect PRO integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.comfoconnect_modbus import PLATFORMS
from homeassistant.components.comfoconnect_modbus.const import DEFAULT_NAME, DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from . import MOCK_ENTRY_DATA, seed_gateway


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.comfoconnect_modbus.async_setup_entry",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_connection() -> MockModbusConnection:
    """Return a mock Modbus connection that answers like a ComfoConnect PRO."""
    connection = MockModbusConnection()
    seed_gateway(connection.for_unit(1))
    return connection


@pytest.fixture
def mock_unit(mock_connection: MockModbusConnection) -> MockModbusUnit:
    """The gateway's unit on the mock connection."""
    return mock_connection.for_unit(1)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a ComfoConnect PRO config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_ENTRY_DATA,
        title=DEFAULT_NAME,
        entry_id="01K0COMFOCONNECTPRO000000",
    )


@pytest.fixture
def mock_get_unit(mock_connection: MockModbusConnection) -> Generator[MagicMock]:
    """Patch `async_get_unit` to return units of the mock connection."""
    with patch(
        "homeassistant.components.comfoconnect_modbus.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ) as mock_get_unit:
        yield mock_get_unit


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return PLATFORMS


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the ComfoConnect PRO integration for testing."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.comfoconnect_modbus.PLATFORMS", platforms):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    return mock_config_entry

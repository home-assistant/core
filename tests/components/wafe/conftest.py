"""Fixtures for the WAFE integration tests."""

from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from modbus_connection import ModbusTcpParams
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture

from homeassistant.components.wafe.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_ENTRY_DATA, MOCK_TITLE, MOCK_UNIT_ID


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.wafe.async_setup_entry",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_connection() -> MockModbusConnection:
    """A fake Modbus TCP connection to a WAFE 201 E in intelligent mode."""
    connection = MockModbusConnection()
    connection.for_unit(1).load_raw(load_json_object_fixture("w201e.json", DOMAIN))
    return connection


@pytest.fixture
def mock_unit(mock_connection: MockModbusConnection) -> MockModbusUnit:
    """The unit the integration talks to."""
    return mock_connection.for_unit(1)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a WAFE config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_UNIT_ID,
        data=MOCK_ENTRY_DATA,
        title=MOCK_TITLE,
    )


@pytest.fixture
def mock_get_unit(mock_connection: MockModbusConnection) -> Generator[MagicMock]:
    """Hand out units on the mock connection when the entry sets up."""
    with patch(
        "homeassistant.components.wafe.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ) as mock_get_unit:
        yield mock_get_unit


@pytest.fixture
def mock_temporary_unit(mock_connection: MockModbusConnection) -> Generator[MagicMock]:
    """Hand out a unit on the mock connection during the config flow."""

    @asynccontextmanager
    async def _get_temporary_unit(
        hass: HomeAssistant, params: ModbusTcpParams, unit_id: int
    ) -> AsyncIterator[MockModbusUnit]:
        yield mock_connection.for_unit(unit_id)

    with patch(
        "homeassistant.components.wafe.config_flow.async_get_temporary_unit",
        side_effect=_get_temporary_unit,
    ) as mock_temporary_unit:
        yield mock_temporary_unit


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_get_unit: MagicMock,
) -> MockConfigEntry:
    """Set up the WAFE integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry

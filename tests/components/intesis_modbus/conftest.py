"""Fixtures for the Intesis Modbus integration tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from modbus_connection.mock import MockModbusConnection
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.intesis_modbus.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_ENTRY_DATA, MOCK_ENTRY_OPTIONS, SINGLE_UNIT_REGISTERS


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.intesis_modbus.async_setup_entry",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def registers() -> dict[int, int]:
    """Registers a test sets differently from the healthy gateway."""
    return {}


@pytest.fixture
def mock_connection(registers: dict[int, int]) -> MockModbusConnection:
    """A fake Modbus connection seeded as a healthy MHI single-unit gateway."""
    connection = MockModbusConnection()
    unit = connection.for_unit(1)
    for address, value in (SINGLE_UNIT_REGISTERS | registers).items():
        unit.holding[address] = value
    return connection


@pytest.fixture
def entry_options() -> dict[str, Any]:
    """The options of the mock config entry."""
    return MOCK_ENTRY_OPTIONS


@pytest.fixture
def mock_config_entry(entry_options: dict[str, Any]) -> MockConfigEntry:
    """Mock a single-unit gateway config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="01JTESTINTESISSINGLE000000",
        data=MOCK_ENTRY_DATA,
        options=entry_options,
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

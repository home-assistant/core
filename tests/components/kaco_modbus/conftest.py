"""Common fixtures for the KACO Modbus tests.

The mock is loaded with a register image captured from a real blueplanet
8.6 TL3 INT, so everything below the connection is the library's own code
reading a real SunSpec map rather than a stubbed device.
"""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from kaco_modbus.testing import BLUEPLANET_86TL3
from modbus_connection.mock import MockModbusConnection
import pytest

from homeassistant.components.kaco_modbus.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import MOCK_MODEL, MOCK_SERIAL, MOCK_USER_INPUT

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.kaco_modbus.async_setup_entry",
        new_callable=AsyncMock,
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_connection() -> MockModbusConnection:
    """A fake Modbus TCP connection serving the captured 8.6 TL3 image."""
    connection = MockModbusConnection()
    connection.for_unit(1).load_raw({"holding": dict(BLUEPLANET_86TL3)})
    return connection


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a KACO Modbus config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
        data=MOCK_USER_INPUT,
        title=MOCK_MODEL,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connection: MockModbusConnection,
) -> MockConfigEntry:
    """Set up the KACO Modbus integration for testing."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.kaco_modbus.async_get_unit",
        side_effect=lambda hass, entry, params, unit_id: mock_connection.for_unit(
            unit_id
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
    return mock_config_entry

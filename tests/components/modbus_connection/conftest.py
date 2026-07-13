"""Common fixtures for the Modbus Connection tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from modbus_connection.mock import MockModbusConnection
import pytest

from homeassistant.components.modbus_connection.const import CONNECTION_TCP, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Prevent the created entry from actually setting up during flow tests."""
    with patch(
        "homeassistant.components.modbus_connection.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_connect(
    mock_modbus_connection: MockModbusConnection,
) -> Generator[AsyncMock]:
    """Patch the backend connect functions to return the mock connection."""
    connect = AsyncMock(return_value=mock_modbus_connection)
    with (
        patch("homeassistant.components.modbus_connection.connect_tcp", connect),
        patch("homeassistant.components.modbus_connection.connect_serial", connect),
    ):
        yield connect


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a TCP connection config entry, already added to hass."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="1.2.3.4:502",
        data={CONF_TYPE: CONNECTION_TCP, CONF_HOST: "1.2.3.4", CONF_PORT: 502},
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_connect: AsyncMock,
) -> MockConfigEntry:
    """Set up the connection entry (loaded).

    Relies on ``mock_config_entry`` already being in hass.
    """
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry

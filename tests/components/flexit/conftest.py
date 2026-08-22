"""Common fixtures for the Flexit tests."""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

from modbus_connection.mock import MockModbusConnection
import pytest

from homeassistant.components.flexit.const import DOMAIN, TYPE_TCP
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_SLAVE, CONF_TYPE

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
async def mock_connect_tcp(
    mock_modbus_connection: MockModbusConnection,
) -> AsyncGenerator[AsyncMock]:
    """Patch connect_tcp to return the in-memory mock connection."""
    await mock_modbus_connection.connect()
    connect = AsyncMock(return_value=mock_modbus_connection)
    with (
        patch("homeassistant.components.flexit.connect_tcp", new=connect),
        patch("homeassistant.components.flexit.config_flow.connect_tcp", new=connect),
    ):
        yield connect


@pytest.fixture
async def mock_connect_serial(
    mock_modbus_connection: MockModbusConnection,
) -> AsyncGenerator[AsyncMock]:
    """Patch connect_serial to return the in-memory mock connection."""
    await mock_modbus_connection.connect()
    connect = AsyncMock(return_value=mock_modbus_connection)
    with (
        patch("homeassistant.components.flexit.connect_serial", new=connect),
        patch(
            "homeassistant.components.flexit.config_flow.connect_serial", new=connect
        ),
    ):
        yield connect


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Flexit",
        data={
            CONF_TYPE: TYPE_TCP,
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 502,
            CONF_SLAVE: 1,
        },
        entry_id="flexit_001",
    )


@pytest.fixture
def mock_serial_config_entry() -> MockConfigEntry:
    """Mock a serial (RTU) config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Flexit",
        data={
            CONF_TYPE: "serial",
            CONF_DEVICE: "/dev/ttyUSB0",
            "baudrate": 9600,
            "bytesize": 8,
            "parity": "N",
            "stopbits": 1,
            CONF_SLAVE: 1,
        },
        entry_id="flexit_002",
    )

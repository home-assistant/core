"""Common fixtures for the Flexit tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from modbus_connection.mock import MockModbusConnection
import pytest

from homeassistant.components.flexit.const import DOMAIN, TYPE_TCP
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_SLAVE, CONF_TYPE

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_create_modbus_connection(
    mock_modbus_connection: MockModbusConnection,
) -> Generator[MagicMock]:
    """Patch the connection factory to return the in-memory mock connection."""
    create_connection = MagicMock(return_value=mock_modbus_connection)
    with (
        patch(
            "homeassistant.components.flexit.create_modbus_connection",
            new=create_connection,
        ),
        patch(
            "homeassistant.components.flexit.config_flow.create_modbus_connection",
            new=create_connection,
        ),
    ):
        yield create_connection


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

"""Common fixtures for the Flexit tests."""

from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from unittest.mock import MagicMock, patch

from modbus_connection.mock import MockModbusUnit
import pytest

from homeassistant.components.flexit.const import CONF_UNIT, DOMAIN, TYPE_TCP
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT, CONF_TYPE

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_get_modbus_unit(
    mock_modbus_unit: MockModbusUnit,
) -> Generator[MagicMock]:
    """Patch the shared unit helper to return the in-memory mock unit."""
    with patch(
        "homeassistant.components.flexit.async_get_unit",
        return_value=mock_modbus_unit,
    ) as get_unit:
        yield get_unit


@pytest.fixture(autouse=True)
def mock_get_temporary_modbus_unit(
    mock_modbus_unit: MockModbusUnit,
) -> Generator[MagicMock]:
    """Patch the temporary unit helper to return the in-memory mock unit."""

    @asynccontextmanager
    async def temporary_unit(*_: object) -> AsyncIterator[MockModbusUnit]:
        yield mock_modbus_unit

    get_temporary_unit = MagicMock(side_effect=temporary_unit)
    with patch(
        "homeassistant.components.flexit.config_flow.async_get_temporary_unit",
        new=get_temporary_unit,
    ):
        yield get_temporary_unit


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
            CONF_UNIT: 1,
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
            "baudrate": 57600,
            CONF_UNIT: 1,
        },
        entry_id="flexit_002",
    )

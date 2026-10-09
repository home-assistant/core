"""Fixtures for the Sunsynk tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from sunsynk.battery import Battery
from sunsynk.grid import Grid
from sunsynk.input import Input
from sunsynk.inverter import Inverter
from sunsynk.load import Load
from sunsynk.user import User

from homeassistant.components.sunsynk.const import (
    CONF_UNIT_ID,
    DOMAIN,
    TYPE_CLOUD,
    TYPE_MODBUS,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_TYPE,
    CONF_USERNAME,
)

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

USERNAME = "test@example.com"
PASSWORD = "test-password"
USER_ID = "281092"

MODBUS_HOST = "192.168.1.217"
MODBUS_SERIAL_NUMBER = "2201234567"
MODBUS_USER_INPUT = {CONF_HOST: MODBUS_HOST, CONF_PORT: 502, CONF_UNIT_ID: 1}


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sunsynk.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_sunsynk_client() -> Generator[AsyncMock]:
    """Mock the Sunsynk API client."""
    with (
        patch(
            "homeassistant.components.sunsynk.SunsynkClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.sunsynk.config_flow.SunsynkClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_user.return_value = User(
            load_json_object_fixture("user.json", DOMAIN)
        )
        client.get_inverters.return_value = [
            Inverter(inverter)
            for inverter in load_json_array_fixture("inverters.json", DOMAIN)
        ]
        client.get_inverter_realtime_battery.side_effect = lambda sn: Battery(
            load_json_object_fixture(
                "battery.json" if sn == "1029384756" else "battery_absent.json",
                DOMAIN,
            )
        )
        client.get_inverter_realtime_grid.side_effect = lambda sn: Grid(
            load_json_object_fixture("grid.json", DOMAIN)
        )
        client.get_inverter_realtime_input.side_effect = lambda sn: Input(
            load_json_object_fixture("input.json", DOMAIN)
        )
        client.get_inverter_realtime_load.side_effect = lambda sn: Load(
            load_json_object_fixture("load.json", DOMAIN)
        )
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=USERNAME,
        data={CONF_TYPE: TYPE_CLOUD, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        unique_id=USER_ID,
        minor_version=2,
    )


@pytest.fixture
def mock_modbus_config_entry() -> MockConfigEntry:
    """Return a mocked config entry for an inverter that uses Modbus."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Inverter {MODBUS_SERIAL_NUMBER}",
        data={CONF_TYPE: TYPE_MODBUS, **MODBUS_USER_INPUT},
        unique_id=MODBUS_SERIAL_NUMBER,
        minor_version=2,
    )


@pytest.fixture
def mock_modbus_unit(mock_modbus_connection: MockModbusConnection) -> MockModbusUnit:
    """Return the unit of the inverter on the in-memory Modbus connection."""
    return mock_modbus_connection.for_unit(1)


@pytest.fixture
def mock_modbus_connection_class(
    mock_modbus_connection: MockModbusConnection, mock_modbus_unit: MockModbusUnit
) -> Generator[MagicMock]:
    """Let the modbus integration hand out units on the in-memory connection.

    The unit has the registers of a 3.6 kW inverter.
    """
    mock_modbus_unit.load_raw(load_json_object_fixture("modbus_registers.json", DOMAIN))
    with patch(
        "homeassistant.components.modbus.connection.ModbusConnection",
        return_value=mock_modbus_connection,
    ) as mock_connection_class:
        yield mock_connection_class

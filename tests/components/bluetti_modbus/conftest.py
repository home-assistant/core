"""Fixtures for the BLUETTI Modbus tests.

The ``mock_modbus_connection`` / ``mock_modbus_unit`` fixtures come from the
``modbus-connection`` library's pytest plugin (registered as a ``pytest11``
entry point).
"""

from collections.abc import AsyncIterator, Generator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import patch

from modbus_connection import ModbusUnit
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest

from homeassistant.components.bluetti_modbus.const import CONF_UNIT_ID, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture

HOST = "1.2.3.4"
PORT = 502
UNIT_ID = 1
ENTRY_ID = "01K3ZZZZZZZZZZZZZZZZZZZZZZ"
# The capture's own serial registers are redacted.
SERIAL = "1234"
SERIAL_ADDRESS = 50206


def bluetti_data(unit_id: int = UNIT_ID) -> dict[str, Any]:
    """Config entry data for a device reached over Modbus TCP."""
    return {
        CONF_HOST: HOST,
        CONF_PORT: PORT,
        CONF_UNIT_ID: unit_id,
    }


def seed_unit(unit: MockModbusUnit) -> None:
    """Seed a mock unit with registers captured from a real Balco260."""
    unit.load_raw(load_json_object_fixture("balco260_registers.json", DOMAIN))
    unit.holding[SERIAL_ADDRESS] = int(SERIAL)


@pytest.fixture(autouse=True)
def mock_shared_connection(
    mock_modbus_connection: MockModbusConnection,
) -> Generator[None]:
    """Hand out units on the seeded mock instead of opening a real connection."""

    @asynccontextmanager
    async def async_temporary_unit(
        hass: HomeAssistant, params: Any, unit_id: int
    ) -> AsyncIterator[ModbusUnit]:
        yield mock_modbus_connection.for_unit(unit_id)

    with (
        patch(
            "homeassistant.components.bluetti_modbus.async_get_unit",
            side_effect=lambda hass, entry, params, unit_id: (
                mock_modbus_connection.for_unit(unit_id)
            ),
        ),
        patch(
            "homeassistant.components.bluetti_modbus.config_flow.async_get_temporary_unit",
            async_temporary_unit,
        ),
    ):
        yield


@pytest.fixture
def mock_modbus_unit(mock_modbus_connection: MockModbusConnection) -> MockModbusUnit:
    """A seeded BLUETTI power station on unit ``UNIT_ID``.

    Overrides the library plugin's ``mock_modbus_unit`` to preload every
    register this device type's fields cover.
    """
    unit = mock_modbus_connection.for_unit(UNIT_ID)
    seed_unit(unit)
    return unit


@pytest.fixture
def mock_config_entry(mock_modbus_unit: MockModbusUnit) -> MockConfigEntry:
    """A BLUETTI Modbus config entry for the seeded device."""
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        unique_id=SERIAL,
        title="Balco260",
        data=bluetti_data(),
    )

"""Tests for the ComfoConnect PRO on core's shared Modbus connections."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from modbus_connection.mock import MockModbusConnection
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.comfoconnect_modbus.const import CONF_UNIT_ID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import MOCK_SERIAL_ENTRY_DATA, seed_gateway


@pytest.fixture
def bus() -> MockModbusConnection:
    """One RS-485 bus with gateways on unit IDs 1 and 2."""
    connection = MockModbusConnection()
    seed_gateway(connection.for_unit(1))
    seed_gateway(connection.for_unit(2))
    return connection


@pytest.fixture
def connection_class(bus: MockModbusConnection) -> Generator[MagicMock]:
    """Stand in for the backend core's modbus helper opens connections with."""
    with patch(
        "homeassistant.components.modbus.connection.ModbusConnection",
        return_value=bus,
    ) as connection_class:
        yield connection_class


async def _set_up_both(hass: HomeAssistant) -> tuple[MockConfigEntry, MockConfigEntry]:
    """Set up the gateways on unit IDs 1 and 2 of the same serial port."""
    first = MockConfigEntry(domain=DOMAIN, data=MOCK_SERIAL_ENTRY_DATA)
    second = MockConfigEntry(
        domain=DOMAIN, data={**MOCK_SERIAL_ENTRY_DATA, CONF_UNIT_ID: 2}
    )
    for entry in (first, second):
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return first, second


async def test_two_gateways_share_one_serial_connection(
    hass: HomeAssistant, connection_class: MagicMock
) -> None:
    """Test two units on one bus load over a single connection."""
    first, second = await _set_up_both(hass)

    assert first.state is ConfigEntryState.LOADED
    assert second.state is ConfigEntryState.LOADED
    connection_class.assert_called_once()

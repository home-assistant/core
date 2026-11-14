"""Tests for the E3/DC diagnostics."""

from collections.abc import Callable
from datetime import timedelta

from e3dc_ess_modbus.model import register
from freezegun.api import FrozenDateTimeFactory
from modbus_connection import IllegalDataAddressError, ModbusConnectionError
from modbus_connection.mock import MockModbusUnit
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.e3dc.const import SCAN_INTERVAL
from homeassistant.core import HomeAssistant


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag == snapshot


async def test_diagnostics_drop_the_serial_number_registers(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    init_integration: MockConfigEntry,
) -> None:
    """Test the raw dump leaves out the serial number's registers."""
    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    holding = diag["raw"]["holding"]
    assert str(register(40035)) in holding
    assert not any(str(register(n)) in holding for n in range(40036, 40052))
    assert str(register(40052)) in holding
    assert diag["serial_number"] == "**REDACTED**"


@pytest.mark.parametrize(
    "fail",
    [
        pytest.param(
            # Register 40068 holds the PV power
            lambda unit: unit.fail_read(register(40068), IllegalDataAddressError()),
            id="refused_read",
        ),
        pytest.param(
            lambda unit: unit.fail_requests(ModbusConnectionError()),
            id="connection_lost",
        ),
    ],
)
async def test_diagnostics_after_failed_poll(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    init_integration: MockConfigEntry,
    mock_unit: MockModbusUnit,
    fail: Callable[[MockModbusUnit], None],
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics report the failed poll and the failed raw read."""
    fail(mock_unit)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag == snapshot

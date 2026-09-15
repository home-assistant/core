"""Test the Sofar Inverter Modbus link tuning."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import (
    ModbusConnectionError,
    ModbusTimeoutError,
    ServerDeviceBusyError,
)
from modbus_connection.mock import MockModbusConnection
import pytest
from sofar_modbus.model import UpdateReport

from homeassistant.components.sofar.const import SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator

GRID_REGISTER = 0x0484

CLEAN_POLLS = 5
"""Polls the tuner wants before it acts on what it measured."""

EARNED_TIMEOUT = 0.5
"""The shortest ask the tuner makes, which a mocked link always earns."""


async def _poll(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, count: int
) -> None:
    """Run the readings coordinator ``count`` times."""
    for _ in range(count):
        freezer.tick(timedelta(seconds=SCAN_INTERVAL))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()


@pytest.mark.usefixtures("init_integration")
async def test_tuner_lowers_the_link_timeout(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """Test a link that answers cleanly is asked for a shorter timeout."""
    unit = mock_connection.for_unit(1)
    assert unit.required_timeout is None

    await _poll(hass, freezer, CLEAN_POLLS)

    assert unit.required_timeout == EARNED_TIMEOUT


@pytest.mark.usefixtures("init_integration")
async def test_tuner_withdraws_the_ask_after_a_timeout(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """Test a timed-out poll hands the link its own timeout back."""
    unit = mock_connection.for_unit(1)
    await _poll(hass, freezer, CLEAN_POLLS)
    assert unit.required_timeout == EARNED_TIMEOUT

    unit.fail_read(GRID_REGISTER, ModbusTimeoutError("stuck"))
    await _poll(hass, freezer, 1)

    assert unit.required_timeout is None


@pytest.mark.usefixtures("init_integration")
async def test_tuner_withdraws_the_ask_when_the_poll_raises(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """Test a poll that times out before anything answers is still heard."""
    unit = mock_connection.for_unit(1)
    await _poll(hass, freezer, CLEAN_POLLS)
    assert unit.required_timeout == EARNED_TIMEOUT

    unit.fail_requests(ModbusTimeoutError("link gone slow"))
    await _poll(hass, freezer, 1)

    assert unit.required_timeout is None


async def test_tuner_hears_a_timeout_only_the_retry_hit(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a component that times out only on the retry still withdraws it."""
    unit = mock_connection.for_unit(1)
    await _poll(hass, freezer, CLEAN_POLLS)
    assert unit.required_timeout == EARNED_TIMEOUT

    async def busy_grid() -> UpdateReport:
        """A first attempt that failed without timing out."""
        return UpdateReport({"state"}, {"grid": ServerDeviceBusyError("busy")})

    init_integration.runtime_data.readings._poll = busy_grid
    unit.fail_read(GRID_REGISTER, ModbusTimeoutError("stuck on retry"))
    await _poll(hass, freezer, 1)

    assert unit.required_timeout is None


async def test_tuner_hears_a_timeout_the_retry_recovered(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a timeout that answered on the second attempt still withdraws it."""
    unit = mock_connection.for_unit(1)
    await _poll(hass, freezer, CLEAN_POLLS)
    assert unit.required_timeout == EARNED_TIMEOUT

    async def timed_out_grid() -> UpdateReport:
        """A first attempt that timed out; the retry finds the unit healthy."""
        return UpdateReport({"state"}, {"grid": ModbusTimeoutError("slow")})

    init_integration.runtime_data.readings._poll = timed_out_grid
    await _poll(hass, freezer, 1)

    assert unit.required_timeout is None


async def test_tuner_hears_a_timeout_the_retry_reported_otherwise(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a retry's own error does not bury the timeout that preceded it."""
    unit = mock_connection.for_unit(1)
    await _poll(hass, freezer, CLEAN_POLLS)
    assert unit.required_timeout == EARNED_TIMEOUT

    async def timed_out_grid() -> UpdateReport:
        """A first attempt that timed out."""
        return UpdateReport({"state"}, {"grid": ModbusTimeoutError("slow")})

    init_integration.runtime_data.readings._poll = timed_out_grid
    unit.fail_read(GRID_REGISTER, ServerDeviceBusyError("busy on retry"))
    await _poll(hass, freezer, 1)

    assert unit.required_timeout is None


async def test_tuner_hears_a_timeout_when_the_retry_loses_the_link(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a link dying during the retry does not bury the earlier timeout."""
    unit = mock_connection.for_unit(1)
    await _poll(hass, freezer, CLEAN_POLLS)
    assert unit.required_timeout == EARNED_TIMEOUT

    async def timed_out_grid() -> UpdateReport:
        """A first attempt that timed out."""
        return UpdateReport({"state"}, {"grid": ModbusTimeoutError("slow")})

    init_integration.runtime_data.readings._poll = timed_out_grid
    unit.fail_read(GRID_REGISTER, ModbusConnectionError("link gone"))
    await _poll(hass, freezer, 1)

    assert unit.required_timeout is None


async def test_diagnostics_report_what_the_tuner_asked(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test the tuning a link settled on reaches the diagnostics dump."""
    await _poll(hass, freezer, CLEAN_POLLS)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)

    assert diag["link"]["tuning"]["timeout"] == EARNED_TIMEOUT

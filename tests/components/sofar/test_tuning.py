"""Test the Sofar Inverter Modbus link tuning."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusTimeoutError
from modbus_connection.mock import MockModbusConnection
import pytest

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

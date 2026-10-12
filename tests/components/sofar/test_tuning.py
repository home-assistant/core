"""Tests for what the Sofar coordinator tells the link tuner."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import (
    ModbusConnectionError,
    ModbusError,
    ModbusTimeoutError,
    ServerDeviceBusyError,
)
from modbus_connection.mock import MockModbusConnection
import pytest
from sofar_modbus.model import UpdateReport

from homeassistant.components.sofar.const import SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed

GRID_REGISTER = 0x0484

SLOW = ModbusTimeoutError("slow")
BUSY = ServerDeviceBusyError("busy")


async def _poll_after_grid_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entry: MockConfigEntry,
    first: ModbusError,
) -> None:
    """Poll once with grid failing its first attempt, so it gets retried."""

    async def first_attempt() -> UpdateReport:
        return UpdateReport({"state"}, {"grid": first})

    entry.runtime_data.readings._poll = first_attempt
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize(
    ("first", "retry"),
    [
        pytest.param(BUSY, SLOW, id="only_the_retry_timed_out"),
        pytest.param(SLOW, None, id="the_retry_recovered"),
        pytest.param(SLOW, BUSY, id="the_retry_failed_otherwise"),
    ],
)
async def test_tuner_hears_a_timeout_either_attempt_hit(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
    first: ModbusError,
    retry: ModbusError | None,
) -> None:
    """Test a timeout on either attempt is what the tuner hears."""
    mock_connection.for_unit(1).fail_read(GRID_REGISTER, retry)

    with patch.object(init_integration.runtime_data.tuner, "observe") as observe:
        await _poll_after_grid_failed(hass, freezer, init_integration, first)

    observe.assert_called_once()
    assert observe.call_args.args[0].failed == {"grid": SLOW}


async def test_tuner_hears_the_timeout_when_the_retry_loses_the_link(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test a link lost on the retry does not bury the earlier timeout."""
    mock_connection.for_unit(1).fail_read(
        GRID_REGISTER, ModbusConnectionError("link gone")
    )

    with patch.object(
        init_integration.runtime_data.tuner, "observe_failure"
    ) as observe_failure:
        await _poll_after_grid_failed(hass, freezer, init_integration, SLOW)

    observe_failure.assert_called_once_with(SLOW)

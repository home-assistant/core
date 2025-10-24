"""Tests for Saunum coordinator error and write paths."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from pymodbus.exceptions import ModbusException
import pytest

from homeassistant.components.saunum.const import (
    DOMAIN,
    REG_CURRENT_TEMP,
    REG_SESSION_ACTIVE,
)
from homeassistant.components.saunum.coordinator import LeilSaunaCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


class MockResult:
    """Successful Modbus read/write result stub mimicking pymodbus response."""

    def __init__(self, registers: list[int] | None = None) -> None:
        """Initialize stub with optional register list."""
        self.registers = registers or []

    def isError(self) -> bool:
        """Return False to signal success (pymodbus style API)."""
        return False


class MockErrorResult(MockResult):
    """Errored Modbus read/write result stub."""

    def __init__(self) -> None:
        """Initialize error stub with empty register list."""
        super().__init__([])

    def isError(self) -> bool:
        """Return True to indicate error condition."""
        return True


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Provide a config entry instance for coordinator tests."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "127.0.0.1", "port": 502},
        unique_id="127.0.0.1:502",
    )
    entry.add_to_hass(hass)
    return entry


def _make_coordinator(
    hass: HomeAssistant, config_entry: MockConfigEntry, client
) -> LeilSaunaCoordinator:
    return LeilSaunaCoordinator(hass, client, 1, config_entry)


@pytest.mark.asyncio
async def test_update_holding_register_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """holding_result.isError triggers UpdateFailed (line 61)."""
    client = MagicMock()
    client.read_holding_registers = AsyncMock(return_value=MockErrorResult())
    coord = _make_coordinator(hass, config_entry, client)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


@pytest.mark.asyncio
async def test_update_sensor_register_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """sensor_result.isError triggers UpdateFailed (lines 80-81)."""
    client = MagicMock()
    # First holding read succeeds with 7 registers
    client.read_holding_registers = AsyncMock(
        side_effect=[MockResult([0, 1, 30, 15, 80, 1, 0]), MockErrorResult()]
    )
    coord = _make_coordinator(hass, config_entry, client)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


@pytest.mark.asyncio
async def test_update_sensor_register_exception(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """ModbusException during sensor read triggers UpdateFailed (lines 96-98)."""
    client = MagicMock()

    async def _read_holding(address: int, count: int, device_id: int):
        if address == REG_SESSION_ACTIVE:
            return MockResult([0, 1, 30, 15, 80, 1, 0])
        raise ModbusException("sensor read failed")

    client.read_holding_registers = AsyncMock(side_effect=_read_holding)
    coord = _make_coordinator(hass, config_entry, client)
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


@pytest.mark.asyncio
async def test_update_alarm_register_error_debug(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Alarm read error path logs info on first occurrence, debug on subsequent."""
    client = MagicMock()
    # holding + sensor succeed, alarm returns error
    client.read_holding_registers = AsyncMock(
        side_effect=[
            MockResult([0, 1, 30, 15, 80, 1, 0]),  # holding - first call
            MockResult([70, 0, 0, 1, 0]),  # sensor - first call
            MockErrorResult(),  # alarm error - first call
            MockResult([0, 1, 30, 15, 80, 1, 0]),  # holding - second call
            MockResult([70, 0, 0, 1, 0]),  # sensor - second call
            MockErrorResult(),  # alarm error - second call
        ]
    )
    coord = _make_coordinator(hass, config_entry, client)

    # First update should log at INFO level
    caplog.clear()
    data = await coord._async_update_data()
    assert data["alarm_door_open"] == 0
    assert "Alarm registers not available on this device" in caplog.text
    assert any(record.levelname == "INFO" for record in caplog.records)

    # Second update should log at DEBUG level
    caplog.clear()
    data = await coord._async_update_data()
    assert data["alarm_door_open"] == 0
    assert "Alarm registers not available" in caplog.text
    assert all(record.levelname == "DEBUG" for record in caplog.records)


@pytest.mark.asyncio
async def test_update_alarm_register_exception_debug(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Alarm ModbusException path logs info on first occurrence, debug on subsequent."""
    client = MagicMock()

    call_count = [0]

    async def _read(address: int, count: int, device_id: int):
        if address == REG_SESSION_ACTIVE:
            return MockResult([0, 1, 30, 15, 80, 1, 0])
        if address == REG_CURRENT_TEMP:
            return MockResult([70, 0, 0, 1, 0])
        call_count[0] += 1
        raise ModbusException("alarm read failed")

    client.read_holding_registers = AsyncMock(side_effect=_read)
    coord = _make_coordinator(hass, config_entry, client)

    # First update should log at INFO level
    caplog.clear()
    data = await coord._async_update_data()
    assert data["alarm_internal_temp"] == 0
    assert "Alarm registers not supported on this device" in caplog.text
    assert any(record.levelname == "INFO" for record in caplog.records)

    # Second update should log at DEBUG level
    caplog.clear()
    data = await coord._async_update_data()
    assert data["alarm_internal_temp"] == 0
    assert "Alarm registers not available on this device" in caplog.text
    assert all(record.levelname == "DEBUG" for record in caplog.records)


@pytest.mark.asyncio
async def test_write_register_modbus_exception(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """write_register ModbusException returns False (line 182)."""
    client = MagicMock()
    client.write_register = AsyncMock(side_effect=ModbusException("write failed"))
    coord = _make_coordinator(hass, config_entry, client)
    success = await coord.async_write_register(4, 80)
    assert not success
    assert "Error writing register" in caplog.text


@pytest.mark.asyncio
async def test_write_register_error_result(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """write_register error result returns False (lines 191-192)."""
    client = MagicMock()
    client.write_register = AsyncMock(return_value=MockErrorResult())
    coord = _make_coordinator(hass, config_entry, client)
    success = await coord.async_write_register(4, 80)
    assert not success
    assert "Error writing register" in caplog.text


@pytest.mark.asyncio
async def test_write_register_success_triggers_refresh(
    hass: HomeAssistant, config_entry: MockConfigEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Successful write triggers sleep and refresh (lines 193-194)."""
    client = MagicMock()
    client.write_register = AsyncMock(return_value=MockResult())
    coord = _make_coordinator(hass, config_entry, client)
    # Patch refresh to observe calls
    coord.async_request_refresh = AsyncMock()
    # Patch sleep to avoid delay
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    success = await coord.async_write_register(4, 80)
    assert success
    coord.async_request_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_success_and_remaining_time(
    hass: HomeAssistant, config_entry: MockConfigEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Successful update path including session start and remaining time calc lines 107-123."""
    client = MagicMock()

    # Two sequential successful update calls to trigger remaining time calculation.
    holding_regs = [1, 1, 30, 15, 80, 1, 0]  # session_active=1, sauna_duration=30 min
    sensor_regs = [70, 0, 10, 1, 0]  # on_time_high=0, on_time_low=10
    alarm_regs = [0, 0, 0, 0, 0, 0]

    # Side effects for reads: holding, sensor, alarm each call.
    async def _read(address: int, count: int, device_id: int):
        if address == REG_SESSION_ACTIVE:
            return MockResult(holding_regs)
        if address == REG_CURRENT_TEMP:
            return MockResult(sensor_regs)
        if address == 200:
            return MockResult(alarm_regs)
        return MockResult([])

    client.read_holding_registers = AsyncMock(side_effect=_read)
    coord = _make_coordinator(hass, config_entry, client)

    # Patch time to simulate 60 seconds elapsed between calls.
    base = datetime.now(tz=UTC)
    # Provide two timestamps for two dt_util.utcnow() calls (first & second update)
    times = [base, base + timedelta(seconds=60), base + timedelta(seconds=60)]
    monkeypatch.setattr(
        "homeassistant.components.saunum.coordinator.dt_util.utcnow",
        lambda: times.pop(0),
    )

    data_first = await coord._async_update_data()
    # First update computes remaining time immediately after setting start time
    assert 0 <= data_first["remaining_time_minutes"] <= 30
    data_second = await coord._async_update_data()
    # Remaining minutes should be less than full duration (30) after 60s.
    assert 0 <= data_second["remaining_time_minutes"] <= 30


@pytest.mark.asyncio
async def test_session_end_clears_start_time(
    hass: HomeAssistant, config_entry: MockConfigEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Session active then inactive clears _session_start_time (lines 107-112)."""
    client = MagicMock()
    seq = [
        # First cycle: active session
        MockResult([1, 1, 10, 5, 75, 1, 0]),
        MockResult([65, 0, 0, 1, 0]),
        MockResult([0, 0, 0, 0, 0, 0]),
        # Second cycle: inactive session
        MockResult([0, 1, 10, 5, 75, 1, 0]),
        MockResult([66, 0, 0, 1, 0]),
        MockResult([0, 0, 0, 0, 0, 0]),
    ]
    client.read_holding_registers = AsyncMock(side_effect=seq)
    coord = _make_coordinator(hass, config_entry, client)
    await coord._async_update_data()
    assert coord._session_start_time is not None
    await coord._async_update_data()
    assert coord._session_start_time is None


@pytest.mark.asyncio
async def test_write_registers_all_success(
    hass: HomeAssistant, config_entry: MockConfigEntry, monkeypatch: pytest.MonkeyPatch
) -> None:
    """async_write_registers success path covers lines 181-191 & refresh once."""
    client = MagicMock()
    client.write_register = AsyncMock(return_value=MockResult())
    coord = _make_coordinator(hass, config_entry, client)
    coord.async_request_refresh = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    ok = await coord.async_write_registers([(4, 80), (5, 1), (6, 0)])
    assert ok is True
    coord.async_request_refresh.assert_awaited_once()
    assert client.write_register.await_count == 3


@pytest.mark.asyncio
async def test_write_registers_partial_failure(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Partial failures set all_ok False but continue writes (lines 181-203)."""
    client = MagicMock()
    # Success, exception, error result
    client.write_register = AsyncMock(
        side_effect=[
            MockResult(),
            ModbusException("write failed"),
            MockErrorResult(),
        ]
    )
    coord = _make_coordinator(hass, config_entry, client)
    coord.async_request_refresh = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    ok = await coord.async_write_registers([(4, 80), (5, 1), (6, 0)])
    assert ok is False
    coord.async_request_refresh.assert_awaited_once()
    # Two error logs expected
    assert caplog.text.count("Error writing register") >= 2


@pytest.mark.asyncio
async def test_write_registers_empty(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Empty writes list short-circuits (line 181 early return)."""
    client = MagicMock()
    coord = _make_coordinator(hass, config_entry, client)
    ok = await coord.async_write_registers([])
    assert ok is True


@pytest.mark.asyncio
async def test_alarm_error_branch_coverage(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Explicitly exercise alarm_result.isError branch for remaining coverage line."""
    client = MagicMock()
    # holding success, sensor success, alarm error result triggers info log on first call
    client.read_holding_registers = AsyncMock(
        side_effect=[
            MockResult([0, 1, 30, 15, 80, 1, 0]),
            MockResult([70, 0, 0, 1, 0]),
            MockErrorResult(),
        ]
    )
    coord = _make_coordinator(hass, config_entry, client)
    data = await coord._async_update_data()
    assert data["alarm_door_open"] == 0
    assert "Alarm registers not available on this device" in caplog.text


@pytest.mark.asyncio
async def test_outer_modbus_exception_communicating_device(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Outer ModbusException after nested reads triggers final UpdateFailed (line 152)."""
    client = MagicMock()

    async def _read(
        address: int, count: int, device_id: int
    ):  # first holding read raises
        raise ModbusException("connection dropped")

    client.read_holding_registers = AsyncMock(side_effect=_read)
    coord = _make_coordinator(hass, config_entry, client)
    with pytest.raises(UpdateFailed) as exc:
        await coord._async_update_data()
    assert "communication error:" in str(exc.value)


@pytest.mark.asyncio
async def test_communication_restored_after_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """Test device communication restored log message."""
    client = MagicMock()

    # First call fails
    call_count = [0]

    async def _read(address: int, count: int, device_id: int):
        call_count[0] += 1
        if call_count[0] == 1:
            raise ModbusException("connection error")
        # Second call succeeds
        mock_response = MagicMock()
        mock_response.isError.return_value = False
        if address == 0:
            mock_response.registers = [0, 0, 60, 10, 2, 0, 0]
        elif address == 100:
            mock_response.registers = [75, 1234, 5678, 3, 0]
        elif address == 200:
            mock_response.registers = [0, 0, 0, 0, 0, 0]
        return mock_response

    client.read_holding_registers = AsyncMock(side_effect=_read)
    coord = _make_coordinator(hass, config_entry, client)

    # First call should fail
    with pytest.raises(UpdateFailed):
        await coord._async_update_data()

    # Second call should succeed and log restoration
    data = await coord._async_update_data()
    assert data is not None
    assert "Device communication restored" in caplog.text


@pytest.mark.asyncio
async def test_write_register_connection_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test write register when client fails to connect."""
    client = MagicMock()
    client.connected = False
    client.connect = AsyncMock(return_value=False)  # Connection fails

    coord = _make_coordinator(hass, config_entry, client)
    result = await coord.async_write_register(1, 100)

    assert result is False


@pytest.mark.asyncio
async def test_write_registers_connection_failure(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test write registers when client fails to connect."""
    client = MagicMock()
    client.connected = False
    client.connect = AsyncMock(return_value=False)  # Connection fails

    coord = _make_coordinator(hass, config_entry, client)
    result = await coord.async_write_registers([(1, 100), (2, 200)])

    assert result is False

"""Tests for the NeoPool time platform."""

import asyncio
from datetime import time as dt_time, timedelta
import gc
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from neopool_modbus.exceptions import NeoPoolConnectionError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.time import DOMAIN as TIME_DOMAIN, SERVICE_SET_VALUE
from homeassistant.const import ATTR_TIME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform as ep, entity_registry as er

from . import setup_integration
from .conftest import MOCK_POOL_DATA, _read_all_timers

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

FLUSH = timedelta(seconds=5)
PARTIAL = timedelta(seconds=2)


def _time_entity_id(
    hass: HomeAssistant, entry: MockConfigEntry, key_lower_suffix: str
) -> str:
    """Resolve a time entity by its trailing unique_id segment."""
    registry = er.async_get(hass)
    entries = [
        e
        for e in er.async_entries_for_config_entry(registry, entry.entry_id)
        if e.domain == TIME_DOMAIN and e.unique_id.endswith(f"_{key_lower_suffix}")
    ]
    assert entries, (
        f"no time entity ending in _{key_lower_suffix} - found: "
        + ", ".join(
            e.unique_id
            for e in er.async_entries_for_config_entry(registry, entry.entry_id)
            if e.domain == TIME_DOMAIN
        )
    )
    return entries[0].entity_id


def _time_entity(hass: HomeAssistant, entity_id: str) -> Any:
    """Return the live NeoPoolTime object for entity_id."""
    for platform in ep.async_get_platforms(hass, "neopool"):
        if entity_id in platform.entities:
            return platform.entities[entity_id]
    raise AssertionError(f"no time entity {entity_id}")


async def _set_time(hass: HomeAssistant, entity_id: str, value: dt_time) -> None:
    await hass.services.async_call(
        TIME_DOMAIN,
        SERVICE_SET_VALUE,
        {"entity_id": entity_id, ATTR_TIME: value},
        blocking=True,
    )


def _set_time_nowait(
    hass: HomeAssistant, entity_id: str, value: dt_time
) -> asyncio.Task[None]:
    """Start a blocking set_value as a task so the freezer can drive the flush.

    A blocking call now awaits the debounced write, which only runs on a
    freezer tick. Awaiting it inline would deadlock, so callers schedule it,
    flush, then await the task to observe the write's outcome.
    """
    return hass.async_create_task(_set_time(hass, entity_id, value))


async def _let_park(hass: HomeAssistant) -> None:
    """Yield enough for a scheduled set_value task to reach its await point.

    ``async_block_till_done`` waits on hass-tracked tasks, so it would block on
    a set_value task intentionally parked before the flush; plain event-loop
    yields let the task register its optimistic state without that wait.
    """
    for _ in range(3):
        await asyncio.sleep(0)


async def _write(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    entity_id: str,
    value: dt_time,
) -> None:
    """Set a value, flush the debounce, and await the write's outcome.

    Raises whatever the debounced write raises (a device error surfaces to the
    blocking caller), matching how a ``blocking: true`` service call behaves.
    """
    task = _set_time_nowait(hass, entity_id, value)
    await _flush(hass, freezer)
    await task


async def _flush(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance past the debounce cooldown and let the pending write run."""
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _advance(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance by less than the cooldown; a pending write must not fire yet.

    Uses event-loop yields rather than ``async_block_till_done`` so a set_value
    task parked on the coalesce future does not stall the advance.
    """
    freezer.tick(PARTIAL)
    async_fire_time_changed(hass)
    await _let_park(hass)


async def _poll(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MagicMock,
    data: dict[str, Any],
) -> None:
    """Push a coordinator poll returning ``data``.

    Filtration timer fields land in coordinator data via read_all_timers, not
    async_read_all, so any filtration1_start/stop override in ``data`` is
    reflected into the mocked timer block (start -> on, stop -> stop).

    Copy ``data`` so the coordinator's in-place merge cannot mutate a shared
    module-level dict.
    """
    mock_client.async_read_all.return_value = dict(data)
    start = data.get("filtration1_start")
    stop = data.get("filtration1_stop")

    def _timers(
        enabled_timers: list[str] | None = None, **_kwargs: Any
    ) -> dict[str, dict[str, Any]]:
        blocks = _read_all_timers(enabled_timers)
        if "filtration1" in blocks:
            if start is not None:
                blocks["filtration1"]["on"] = start
            if stop is not None:
                blocks["filtration1"]["stop"] = stop
        return blocks

    mock_client.read_all_timers.side_effect = _timers
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_native_value_decodes_seconds_since_midnight(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Coordinator seconds become HH:MM:SS state."""
    await setup_integration(hass, mock_config_entry_timers)
    await _poll(
        hass,
        freezer,
        mock_neopool_client,
        {**MOCK_POOL_DATA, "filtration1_start": 6 * 3600 + 30 * 60},
    )

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "06:30:00"


async def test_native_value_returns_none_when_data_missing(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Missing coordinator key surfaces as 'unknown'."""
    await setup_integration(hass, mock_config_entry_timers)
    mock_neopool_client.read_all_timers.side_effect = None
    mock_neopool_client.read_all_timers.return_value = {
        "filtration1": {
            "enable": 0,
            "on": None,
            "interval": None,
            "stop": None,
            "period": None,
            "countdown": 0,
        }
    }
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"


async def test_native_value_handles_out_of_range_seconds(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Values >= 86400 wrap modulo 86400."""
    await setup_integration(hass, mock_config_entry_timers)
    await _poll(
        hass,
        freezer,
        mock_neopool_client,
        {**MOCK_POOL_DATA, "filtration1_start": 86400 + 3600},
    )

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "01:00:00"


async def test_set_value_on_start_writes_timer(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Setting *_start passes only the on endpoint; the library holds the stop."""
    await setup_integration(hass, mock_config_entry_timers)
    await _poll(hass, freezer, mock_neopool_client, MOCK_POOL_DATA)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    mock_neopool_client.write_timer.reset_mock()
    await _write(hass, freezer, entity_id, dt_time(6, 0))

    assert mock_neopool_client.write_timer.await_count == 1
    timer_name, payload = mock_neopool_client.write_timer.await_args.args
    assert timer_name == "filtration1"
    assert payload == {"on": 6 * 3600}


async def test_set_value_on_stop_writes_timer(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Setting *_stop passes only the stop endpoint; the library holds the on."""
    await setup_integration(hass, mock_config_entry_timers)
    await _poll(hass, freezer, mock_neopool_client, MOCK_POOL_DATA)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_stop")
    mock_neopool_client.write_timer.reset_mock()
    await _write(hass, freezer, entity_id, dt_time(10, 0))

    assert mock_neopool_client.write_timer.await_count == 1
    timer_name, payload = mock_neopool_client.write_timer.await_args.args
    assert timer_name == "filtration1"
    assert payload == {"stop": 10 * 3600}


async def test_pending_value_shown_optimistically_before_write(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """State surfaces the requested value while the debounce is in flight."""
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    task = _set_time_nowait(hass, entity_id, dt_time(6, 0))
    await _advance(hass, freezer)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "06:00:00"
    mock_neopool_client.write_timer.assert_not_awaited()

    await _flush(hass, freezer)
    await task


@pytest.mark.parametrize(
    "write_error",
    [
        pytest.param(NeoPoolConnectionError("boom"), id="lib-connection-error"),
        pytest.param(TimeoutError("boom"), id="timeout"),
        pytest.param(OSError("boom"), id="os-error"),
    ],
)
async def test_set_value_maps_communication_error_to_home_assistant_error(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    write_error: Exception,
) -> None:
    """A failed timer write surfaces to the blocking caller as HomeAssistantError."""
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    mock_neopool_client.write_timer.side_effect = write_error

    task = _set_time_nowait(hass, entity_id, dt_time(6, 0))
    await _flush(hass, freezer)
    with pytest.raises(HomeAssistantError) as err:
        await task

    assert err.value.translation_key == "modbus_communication_error"
    mock_neopool_client.write_timer.assert_awaited_once()


async def test_unexpected_write_error_reaches_caller(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An unexpected write error surfaces unchanged, not as a comm error."""
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    mock_neopool_client.write_timer.side_effect = ValueError("boom")

    task = _set_time_nowait(hass, entity_id, dt_time(6, 0))
    await _flush(hass, freezer)
    with pytest.raises(ValueError, match="boom"):
        await task


async def test_post_write_merge_failure_reaches_caller(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A raise after a successful device write surfaces unchanged."""
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    mock_neopool_client.write_timer.reset_mock()

    task = _set_time_nowait(hass, entity_id, dt_time(6, 0))
    with patch.object(
        mock_config_entry_timers.runtime_data,
        "async_set_updated_data",
        side_effect=RuntimeError("merge boom"),
    ):
        await _flush(hass, freezer)
        with pytest.raises(RuntimeError, match="merge boom"):
            await task


async def test_optimistic_state_rolls_back_on_write_failure(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed write rolls the optimistic state back to the device reading."""
    await setup_integration(hass, mock_config_entry_timers)
    await _poll(
        hass,
        freezer,
        mock_neopool_client,
        {**MOCK_POOL_DATA, "filtration1_start": 6 * 3600},
    )

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    mock_neopool_client.write_timer.side_effect = NeoPoolConnectionError("boom")

    task = _set_time_nowait(hass, entity_id, dt_time(8, 0))
    await _let_park(hass)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "08:00:00"

    await _flush(hass, freezer)
    with pytest.raises(HomeAssistantError):
        await task

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "06:00:00"


async def test_rapid_set_value_coalesces_via_debounce(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Sibling start/stop are independent single-endpoint writes to one block."""
    await setup_integration(hass, mock_config_entry_timers)
    await _poll(
        hass,
        freezer,
        mock_neopool_client,
        {**MOCK_POOL_DATA, "filtration1_start": 0, "filtration1_stop": 0},
    )

    start_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    stop_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_stop")

    mock_neopool_client.write_timer.reset_mock()
    start_task = _set_time_nowait(hass, start_id, dt_time(6, 0))
    stop_task = _set_time_nowait(hass, stop_id, dt_time(10, 0))
    await _flush(hass, freezer)
    await asyncio.gather(start_task, stop_task)

    assert mock_neopool_client.write_timer.await_count == 2
    payloads = [
        call.args[1] for call in mock_neopool_client.write_timer.await_args_list
    ]
    assert {"on": 6 * 3600} in payloads
    assert {"stop": 10 * 3600} in payloads
    assert all(
        call.args[0] == "filtration1"
        for call in mock_neopool_client.write_timer.await_args_list
    )


async def test_sibling_writes_to_same_block_are_serialized(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Concurrent start/stop writes to one block never overlap in the library.

    write_timer is a read-modify-write of the shared block, so overlapping
    sibling writes could read a stale endpoint and clobber each other. A
    per-block lock must serialize them: the in-flight count never exceeds one.
    """
    await setup_integration(hass, mock_config_entry_timers)
    await _poll(
        hass,
        freezer,
        mock_neopool_client,
        {**MOCK_POOL_DATA, "filtration1_start": 0, "filtration1_stop": 0},
    )

    start_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    stop_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_stop")

    in_flight = 0
    max_in_flight = 0

    async def _tracking_write(block: str, timer_data: dict[str, Any]) -> bool:
        nonlocal in_flight, max_in_flight
        in_flight += 1
        max_in_flight = max(max_in_flight, in_flight)
        # Yield so a second write not held by the lock would overlap here.
        await asyncio.sleep(0)
        in_flight -= 1
        return True

    mock_neopool_client.write_timer.reset_mock()
    mock_neopool_client.write_timer.side_effect = _tracking_write

    start_task = _set_time_nowait(hass, start_id, dt_time(6, 0))
    stop_task = _set_time_nowait(hass, stop_id, dt_time(10, 0))
    await _flush(hass, freezer)
    await asyncio.gather(start_task, stop_task)

    assert mock_neopool_client.write_timer.await_count == 2
    assert max_in_flight == 1


async def test_repeated_set_value_writes_only_latest(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Two quick set_value calls debounce to a single write of the last value."""
    await setup_integration(hass, mock_config_entry_timers)
    await _poll(hass, freezer, mock_neopool_client, MOCK_POOL_DATA)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    mock_neopool_client.write_timer.reset_mock()

    task1 = _set_time_nowait(hass, entity_id, dt_time(5, 0))
    task2 = _set_time_nowait(hass, entity_id, dt_time(6, 0))
    await _flush(hass, freezer)
    await asyncio.gather(task1, task2)

    assert mock_neopool_client.write_timer.await_count == 1
    _timer_name, payload = mock_neopool_client.write_timer.await_args.args
    assert payload == {"on": 6 * 3600}


async def test_settle_restarts_timer(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Each edit restarts the timer; the write fires after the last edit."""
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    mock_neopool_client.write_timer.reset_mock()

    task1 = _set_time_nowait(hass, entity_id, dt_time(5, 0))
    await _advance(hass, freezer)
    task2 = _set_time_nowait(hass, entity_id, dt_time(6, 0))
    await _advance(hass, freezer)

    mock_neopool_client.write_timer.assert_not_awaited()

    await _flush(hass, freezer)
    await asyncio.gather(task1, task2)

    assert mock_neopool_client.write_timer.await_count == 1
    _timer_name, payload = mock_neopool_client.write_timer.await_args.args
    assert payload == {"on": 6 * 3600}


async def test_no_write_when_settled_value_unchanged(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Setting the value the device already holds writes nothing.

    The settled seconds equal the decoded register, so the EEPROM cycle is
    skipped and the optimistic state falls back to the device reading.
    """
    await setup_integration(hass, mock_config_entry_timers)
    await _poll(
        hass,
        freezer,
        mock_neopool_client,
        {**MOCK_POOL_DATA, "filtration1_start": 6 * 3600},
    )

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    mock_neopool_client.write_timer.reset_mock()
    await _write(hass, freezer, entity_id, dt_time(6, 0))

    mock_neopool_client.write_timer.assert_not_awaited()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "06:00:00"


async def test_coalesced_callers_all_succeed_together(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Three quick set_value calls collapse to one write and all callers succeed."""
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    mock_neopool_client.write_timer.reset_mock()

    tasks = [
        _set_time_nowait(hass, entity_id, value)
        for value in (dt_time(5, 0), dt_time(5, 30), dt_time(6, 0))
    ]
    await _flush(hass, freezer)
    results = await asyncio.gather(*tasks)

    assert mock_neopool_client.write_timer.await_count == 1
    assert results == [None, None, None]


async def test_coalesced_callers_all_raise_together(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed coalesced write raises for every caller in the debounce window."""
    mock_neopool_client.write_timer.side_effect = NeoPoolConnectionError("boom")
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    mock_neopool_client.write_timer.reset_mock()

    tasks = [
        _set_time_nowait(hass, entity_id, value)
        for value in (dt_time(5, 0), dt_time(5, 30), dt_time(6, 0))
    ]
    await _flush(hass, freezer)
    results = await asyncio.gather(*tasks, return_exceptions=True)

    assert mock_neopool_client.write_timer.await_count == 1
    assert all(isinstance(r, HomeAssistantError) for r in results)


async def test_external_cancel_propagates_but_spares_coalesced_caller(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Cancelling one caller re-raises for it but spares the coalesced batch."""
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    mock_neopool_client.write_timer.reset_mock()

    victim = _set_time_nowait(hass, entity_id, dt_time(6, 0))
    survivor = _set_time_nowait(hass, entity_id, dt_time(6, 0))
    await _let_park(hass)

    victim.cancel()
    with pytest.raises(asyncio.CancelledError):
        await victim

    await _flush(hass, freezer)
    await survivor
    mock_neopool_client.write_timer.assert_awaited_once()


async def test_failed_write_survives_a_cancelled_coalesced_caller(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed coalesced write raises for the survivor and logs no warning.

    Two callers share one coalesce future; one is cancelled before the delayed
    write fails. Cancelling a caller makes asyncio.shield attach its own logger
    to the shared future, so failing it via set_exception would be reported as
    an unretrieved error at teardown. The write instead carries its outcome as
    the future's result, so the survivor still re-raises the device error and
    no "exception in shielded future" warning is logged.
    """
    in_write = asyncio.Event()
    release = asyncio.Event()

    async def _blocking_boom(block: str, timer_data: dict[str, Any]) -> bool:
        in_write.set()
        await release.wait()
        raise NeoPoolConnectionError("boom")

    mock_neopool_client.write_timer = AsyncMock(side_effect=_blocking_boom)
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")

    victim = _set_time_nowait(hass, entity_id, dt_time(6, 0))
    survivor = _set_time_nowait(hass, entity_id, dt_time(6, 0))
    await _let_park(hass)
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await in_write.wait()

    victim.cancel()
    with pytest.raises(asyncio.CancelledError):
        await victim

    release.set()
    with pytest.raises(HomeAssistantError):
        await survivor
    await hass.async_block_till_done()

    gc.collect()
    await asyncio.sleep(0)

    assert "exception in shielded future" not in caplog.text
    assert "exception was never retrieved" not in caplog.text


async def test_write_queued_during_flush_gets_its_own_outcome(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A set_value arriving mid-flush writes on its own, not the in-flight batch."""
    in_write = asyncio.Event()
    release = asyncio.Event()
    seen: list[int] = []

    async def _gated_write(block: str, timer_data: dict[str, Any]) -> bool:
        seen.append(timer_data["on"])
        if len(seen) == 1:
            in_write.set()
            await release.wait()
        return True

    mock_neopool_client.write_timer = AsyncMock(side_effect=_gated_write)
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    seen.clear()

    first = _set_time_nowait(hass, entity_id, dt_time(7, 0))
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await in_write.wait()

    second = _set_time_nowait(hass, entity_id, dt_time(8, 0))
    await _let_park(hass)

    release.set()
    await first
    await _flush(hass, freezer)
    await second

    assert seen == [7 * 3600, 8 * 3600]
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "08:00:00"


async def test_same_value_queued_during_flush_still_resolves(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A second set_value of the same value mid-flush still gets an outcome."""
    in_write = asyncio.Event()
    release = asyncio.Event()
    seen: list[int] = []

    async def _gated_write(block: str, timer_data: dict[str, Any]) -> bool:
        seen.append(timer_data["on"])
        if len(seen) == 1:
            in_write.set()
            await release.wait()
        return True

    mock_neopool_client.write_timer = AsyncMock(side_effect=_gated_write)
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    seen.clear()

    first = _set_time_nowait(hass, entity_id, dt_time(7, 0))
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await in_write.wait()

    second = _set_time_nowait(hass, entity_id, dt_time(7, 0))
    await _let_park(hass)

    release.set()
    await first
    await _flush(hass, freezer)
    await second

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "07:00:00"


async def test_optimistic_value_survives_overlapping_flush(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A newer optimistic value is not clobbered by an in-flight older write."""
    in_write = asyncio.Event()
    release = asyncio.Event()
    seen: list[int] = []

    async def _gated_write(block: str, timer_data: dict[str, Any]) -> bool:
        seen.append(timer_data["on"])
        if len(seen) == 1:
            in_write.set()
            await release.wait()
        return True

    mock_neopool_client.write_timer = AsyncMock(side_effect=_gated_write)
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    seen.clear()

    first = _set_time_nowait(hass, entity_id, dt_time(7, 0))
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await in_write.wait()

    second = _set_time_nowait(hass, entity_id, dt_time(8, 0))
    await _let_park(hass)

    release.set()
    await first
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "08:00:00"

    await _flush(hass, freezer)
    await second
    assert seen == [7 * 3600, 8 * 3600]
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "08:00:00"


async def test_write_works_after_entity_id_change(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A write still reaches the device after the entity is renamed.

    Changing the entity ID removes and re-adds the same object. If removal
    leaves the removing flag set, every later flush aborts and the write never
    reaches the device, so the write must run against the new entity ID.
    """
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    new_entity_id = f"{entity_id}_renamed"
    entity_registry.async_update_entity(entity_id, new_entity_id=new_entity_id)
    await hass.async_block_till_done()
    assert hass.states.get(new_entity_id) is not None

    mock_neopool_client.write_timer.reset_mock()
    await _write(hass, freezer, new_entity_id, dt_time(6, 0))

    mock_neopool_client.write_timer.assert_awaited_once()
    state = hass.states.get(new_entity_id)
    assert state is not None
    assert state.state == "06:00:00"


async def test_pending_write_dropped_on_remove(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unloading cancels an un-elapsed write and releases the awaiting caller."""
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    task = _set_time_nowait(hass, entity_id, dt_time(6, 0))
    await _let_park(hass)

    await hass.config_entries.async_unload(mock_config_entry_timers.entry_id)
    await _flush(hass, freezer)

    await task
    mock_neopool_client.write_timer.assert_not_awaited()


async def test_flush_aborts_when_removed_while_holding_lock(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A flush that finds the entity removed after winning the lock aborts."""
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    entity = _time_entity(hass, entity_id)

    await entity._flush_lock.acquire()
    task = _set_time_nowait(hass, entity_id, dt_time(6, 0))
    await _let_park(hass)
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await _let_park(hass)

    entity._removing = True
    entity._flush_lock.release()
    await task

    mock_neopool_client.write_timer.assert_not_awaited()
    entity._removing = False


async def test_inflight_write_skips_coordinator_on_remove(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A write already in flight when the entity is removed skips the coordinator."""
    in_write = asyncio.Event()
    release = asyncio.Event()

    async def _blocking_write(block: str, timer_data: dict[str, Any]) -> bool:
        in_write.set()
        await release.wait()
        return True

    mock_neopool_client.write_timer = AsyncMock(side_effect=_blocking_write)
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")
    task = _set_time_nowait(hass, entity_id, dt_time(6, 0))
    await _let_park(hass)

    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await in_write.wait()

    with patch.object(
        mock_config_entry_timers.runtime_data, "async_set_updated_data"
    ) as mock_update:
        await hass.config_entries.async_unload(mock_config_entry_timers.entry_id)
        release.set()
        await hass.async_block_till_done(wait_background_tasks=True)

    await task
    mock_neopool_client.write_timer.assert_awaited_once()
    mock_update.assert_not_called()


async def test_client_close_waits_for_all_overlapping_flushes(
    hass: HomeAssistant,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Removal cancels every overlapping flush, not just the most recent one."""
    in_write = asyncio.Event()
    write_active = False
    close_saw_write_active: bool | None = None

    async def _blocking_write(block: str, timer_data: dict[str, Any]) -> bool:
        nonlocal write_active
        write_active = True
        in_write.set()
        try:
            await asyncio.Event().wait()
            return True
        finally:
            write_active = False

    async def _record_close() -> None:
        nonlocal close_saw_write_active
        close_saw_write_active = write_active

    mock_neopool_client.write_timer = AsyncMock(side_effect=_blocking_write)
    mock_neopool_client.close = AsyncMock(side_effect=_record_close)
    await setup_integration(hass, mock_config_entry_timers)

    entity_id = _time_entity_id(hass, mock_config_entry_timers, "filtration1_start")

    first = _set_time_nowait(hass, entity_id, dt_time(7, 0))
    await _let_park(hass)
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await in_write.wait()

    second = _set_time_nowait(hass, entity_id, dt_time(8, 0))
    await _let_park(hass)
    freezer.tick(FLUSH)
    async_fire_time_changed(hass)
    await _let_park(hass)

    assert await hass.config_entries.async_unload(mock_config_entry_timers.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    await first
    await second
    mock_neopool_client.close.assert_awaited_once()
    assert close_saw_write_active is False


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_neopool_client")
async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry_timers: MockConfigEntry,
) -> None:
    """Snapshot every entity registered by the time platform."""
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.TIME]):
        await setup_integration(hass, mock_config_entry_timers)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_timers.entry_id
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_setup_when_modules_absent(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry_timers: MockConfigEntry,
    mock_neopool_client: MagicMock,
    minimal_pool_data: dict[str, Any],
) -> None:
    """Snapshot the time entities registered when no modules are present."""
    mock_neopool_client.async_read_all.return_value = minimal_pool_data
    with patch("homeassistant.components.neopool.PLATFORMS", [Platform.TIME]):
        await setup_integration(hass, mock_config_entry_timers)
    await snapshot_platform(
        hass, entity_registry, snapshot, mock_config_entry_timers.entry_id
    )

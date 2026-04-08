"""Tests for HIVIGroupCoordinator (mocked device_manager / discovery)."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.hivi_speaker.const import DOMAIN
import homeassistant.components.hivi_speaker.group_coordinator as gc_module
from homeassistant.components.hivi_speaker.group_coordinator import HIVIGroupCoordinator
from homeassistant.core import EventBus, HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from tests.common import MockConfigEntry


class _GroupCoordinatorAsyncioProxy:
    """Swap only `sleep` on group_coordinator's `asyncio` name; delegate everything else (e.g. CancelledError).

    MagicMock(wraps=asyncio) breaks `except asyncio.CancelledError` because CancelledError becomes a Mock.
    """

    __slots__ = ("_sleep",)

    def __init__(self, sleep_impl):
        self._sleep = sleep_impl

    @property
    def sleep(self):
        return self._sleep

    def __getattr__(self, name: str):
        return getattr(asyncio, name)


@contextmanager
def _patch_group_coordinator_asyncio_sleep(sleep_impl):
    """Mock sleep only inside group_coordinator (replace module-local `asyncio` binding).

    Do not use patch(..., 'group_coordinator.asyncio.sleep') — that mutates stdlib
    asyncio and can deadlock HA's event loop.
    """
    with patch.object(
        gc_module, "asyncio", _GroupCoordinatorAsyncioProxy(sleep_impl)
    ):
        yield


async def _gc_sleep_zero(_delay: float = 0) -> None:
    await asyncio.sleep(0)


# HA often freezes/patches time so coordinator `datetime.now(tz=UTC)` and test
# `start_time` can mix naive vs aware and break subtraction in polling.
_POLL_OP_START = datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC)
_POLL_OP_NOW = datetime(2020, 1, 1, 12, 0, 5, tzinfo=UTC)


class _FixedDatetimeModuleForPoll:
    UTC = UTC

    @staticmethod
    def now(tz=None):
        return _POLL_OP_NOW


@contextmanager
def _patch_group_coordinator_datetime_for_poll():
    with patch.object(gc_module, "datetime", _FixedDatetimeModuleForPoll):
        yield


@pytest.fixture
def coordinator(hass: HomeAssistant) -> HIVIGroupCoordinator:
    dm = MagicMock()
    ds = MagicMock()
    return HIVIGroupCoordinator(hass=hass, device_manager=dm, discovery_scheduler=ds)


def test_generate_operation_id(coordinator: HIVIGroupCoordinator) -> None:
    oid = coordinator._generate_operation_id(
        {"type": "set_slave", "master": "m1", "slave": "s1"}
    )
    assert oid == "set_slave_master_m1_slave_s1"


def test_check_conflicts_empty_pending(coordinator: HIVIGroupCoordinator) -> None:
    out = coordinator._check_conflicting_operations(
        {"type": "set_slave", "master": "a", "slave": "b"}
    )
    assert out["has_conflict"] is False


def test_check_conflicts_master_is_existing_slave(coordinator: HIVIGroupCoordinator) -> None:
    coordinator._pending_operations["op1"] = {
        "master": "big",
        "slave": "small",
        "status": "pending",
    }
    out = coordinator._check_conflicting_operations(
        {"type": "set_slave", "master": "small", "slave": "other"}
    )
    assert out["has_conflict"] is True
    assert out["conflict_type"] == "master_is_existing_slave"


def test_check_conflicts_slave_is_existing_master(coordinator: HIVIGroupCoordinator) -> None:
    coordinator._pending_operations["op1"] = {
        "master": "big",
        "slave": "small",
        "status": "pending",
    }
    out = coordinator._check_conflicting_operations(
        {"type": "set_slave", "master": "x", "slave": "big"}
    )
    assert out["has_conflict"] is True
    assert "master" in out["conflict_reason"]


def test_check_conflicts_slave_is_existing_slave(coordinator: HIVIGroupCoordinator) -> None:
    coordinator._pending_operations["op1"] = {
        "master": "big",
        "slave": "small",
        "status": "pending",
    }
    out = coordinator._check_conflicting_operations(
        {"type": "set_slave", "master": "x", "slave": "small"}
    )
    assert out["has_conflict"] is True


def test_find_operation_helpers(coordinator: HIVIGroupCoordinator) -> None:
    coordinator._pending_operations["a"] = {"master": "m", "slave": "s"}
    assert coordinator._find_operation_by_slave("s") == "a"
    assert coordinator._find_operation_by_device("m") == "a"
    assert coordinator._find_operation_by_slave("nope") is None


async def test_async_handle_discovery_request_accepts_and_invokes_callback(
    coordinator: HIVIGroupCoordinator,
) -> None:
    cb = AsyncMock()
    data = {"type": "set_slave", "master": "m", "slave": "s", "expected_state": "slave"}
    out = await coordinator.async_handle_discovery_request(data, cb)
    assert out.get("accepted") is True
    assert cb.await_count >= 1
    statuses = [c.args[0].get("status") for c in cb.await_args_list]
    assert "accepted" in statuses


async def test_async_handle_discovery_request_rejects_duplicate(
    coordinator: HIVIGroupCoordinator,
) -> None:
    data = {"type": "set_slave", "master": "m", "slave": "s"}
    await coordinator.async_handle_discovery_request(data, None)
    cb = AsyncMock()
    out = await coordinator.async_handle_discovery_request(data, cb)
    assert out["status"] == "rejected"
    assert out["extra"]["reason"] == "operation_already_exists"
    cb.assert_awaited_once()


async def test_async_handle_discovery_request_rejects_conflict(
    coordinator: HIVIGroupCoordinator,
) -> None:
    coordinator._pending_operations["x"] = {
        "type": "set_slave",
        "master": "m0",
        "slave": "s0",
        "status": "pending",
    }
    cb = AsyncMock()
    out = await coordinator.async_handle_discovery_request(
        {"type": "set_slave", "master": "s0", "slave": "s9"},
        cb,
    )
    assert out["status"] == "rejected"
    assert out["extra"]["reason"] == "conflicting_operation"
    cb.assert_awaited_once()


async def test_async_set_slave_speaker_starts_processing(
    hass: HomeAssistant,
    coordinator: HIVIGroupCoordinator,
) -> None:
    with patch.object(hass, "async_create_task") as mock_ct:
        out = await coordinator.async_set_slave_speaker(
            {
                "type": "set_slave",
                "master": "m",
                "slave": "s",
                "expected_state": "slave",
            },
            None,
        )
    assert out.get("accepted") is True
    mock_ct.assert_called_once()


async def test_async_remove_slave_speaker_starts_processing(
    hass: HomeAssistant,
    coordinator: HIVIGroupCoordinator,
) -> None:
    with patch.object(hass, "async_create_task"):
        out = await coordinator.async_remove_slave_speaker("m", "s", None)
    assert out.get("accepted") is True


async def test_async_start_and_stop_wires_listeners(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="HiVi", data={})
    entry.add_to_hass(hass)
    dm = MagicMock()
    ds = MagicMock()
    coord = HIVIGroupCoordinator(hass, dm, ds)
    with (
        patch.object(EventBus, "async_listen") as mock_listen,
        patch(
            "homeassistant.components.hivi_speaker.group_coordinator.async_dispatcher_connect",
            return_value=MagicMock(),
        ) as mock_dc,
    ):
        await coord.async_start()
    assert mock_listen.call_count == 2
    mock_dc.assert_called_once()

    coord._poll_tasks["t1"] = MagicMock(done=MagicMock(return_value=True))
    await coord.async_stop()
    assert coord._coordinator_running is False
    assert not coord._dispatcher_connections


async def test_async_stop_cancels_running_poll_tasks(hass: HomeAssistant) -> None:
    dm = MagicMock()
    ds = MagicMock()
    coord = HIVIGroupCoordinator(hass, dm, ds)

    # Use a long sleep so the task stays "running" until cancelled.
    # asyncio.Event.wait() can fail to unblock promptly on cancel in some loop builds,
    # which would hang async_stop's `await task` after task.cancel().
    task = hass.async_create_task(asyncio.sleep(3600.0))
    await asyncio.sleep(0)
    coord._poll_tasks["op"] = task
    coord._coordinator_running = True
    await coord.async_stop()
    assert task.cancelled() or task.done()


async def test_async_start_operation_processing_missing_op(
    coordinator: HIVIGroupCoordinator,
) -> None:
    await coordinator.async_start_operation_processing("nonexistent")


async def test_log_detailed_conflict_analysis(coordinator: HIVIGroupCoordinator) -> None:
    coordinator._pending_operations["p"] = {"master": "a", "slave": "b"}
    coordinator._log_detailed_conflict_analysis({"master": "b", "slave": "a"})


@pytest.fixture
def full_params() -> dict:
    return {
        "slave_ip": "192.168.1.10",
        "ssid": "wifi",
        "wifi_channel": "6",
        "auth": "wpa2",
        "encry": "aes",
        "psk": "secret",
        "master_ip": "192.168.1.1",
        "uuid": "dev-uuid",
    }


async def test_execute_operation_set_slave_missing_params(
    coordinator: HIVIGroupCoordinator,
) -> None:
    op = {"type": "set_slave", "data": {"params": {"slave_ip": "only"}}}
    assert await coordinator._execute_operation(op) is False


async def test_execute_operation_remove_slave_missing_params(
    coordinator: HIVIGroupCoordinator,
) -> None:
    op = {"type": "remove_slave", "data": {"params": {}}}
    assert await coordinator._execute_operation(op) is False


async def test_execute_operation_unknown_type(coordinator: HIVIGroupCoordinator) -> None:
    assert await coordinator._execute_operation({"type": "nope", "data": {}}) is False


async def test_execute_operation_set_slave_success(
    coordinator: HIVIGroupCoordinator,
    full_params: dict,
) -> None:
    inner = MagicMock()
    inner.connect_slave_to_master = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=inner)
    ctx.__aexit__ = AsyncMock(return_value=None)
    op = {"type": "set_slave", "data": {"params": full_params}}
    with patch(
        "homeassistant.components.hivi_speaker.group_coordinator.HivicoClient",
        return_value=ctx,
    ):
        assert await coordinator._execute_operation(op) is True
    inner.connect_slave_to_master.assert_awaited_once()


async def test_execute_operation_set_slave_client_error(
    coordinator: HIVIGroupCoordinator,
    full_params: dict,
) -> None:
    inner = MagicMock()
    inner.connect_slave_to_master = AsyncMock(side_effect=OSError("fail"))
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=inner)
    ctx.__aexit__ = AsyncMock(return_value=None)
    op = {"type": "set_slave", "data": {"params": full_params}}
    with patch(
        "homeassistant.components.hivi_speaker.group_coordinator.HivicoClient",
        return_value=ctx,
    ):
        assert await coordinator._execute_operation(op) is False


async def test_execute_operation_remove_slave_success(
    coordinator: HIVIGroupCoordinator,
) -> None:
    inner = MagicMock()
    inner.remove_slave_from_group = AsyncMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=inner)
    ctx.__aexit__ = AsyncMock(return_value=None)
    op = {
        "type": "remove_slave",
        "data": {"params": {"master_ip": "10.0.0.1", "slave_ip_ra0": "10.0.0.2"}},
    }
    with patch(
        "homeassistant.components.hivi_speaker.group_coordinator.HivicoClient",
        return_value=ctx,
    ):
        assert await coordinator._execute_operation(op) is True


async def test_async_start_operation_processing_execute_fails(
    coordinator: HIVIGroupCoordinator,
    full_params: dict,
) -> None:
    op_id = coordinator._generate_operation_id(
        {"type": "set_slave", "master": "m1", "slave": "s1"}
    )
    coordinator._pending_operations[op_id] = {
        "type": "set_slave",
        "master": "m1",
        "slave": "s1",
        "start_time": datetime.now(tz=UTC),
        "expected_state": "slave",
        "retry_count": 0,
        "last_check": None,
        "status": "pending",
        "data": {
            "type": "set_slave",
            "master": "m1",
            "slave": "s1",
            "params": full_params,
        },
        "request_callback": AsyncMock(),
    }
    with (
        patch.object(
            coordinator, "_execute_operation", AsyncMock(return_value=False)
        ),
        patch.object(coordinator, "_handle_operation_failed", new_callable=AsyncMock),
    ):
        await coordinator.async_start_operation_processing(op_id)


async def test_async_start_operation_processing_success_schedules_poll(
    hass: HomeAssistant,
    coordinator: HIVIGroupCoordinator,
    full_params: dict,
) -> None:
    op_id = coordinator._generate_operation_id(
        {"type": "set_slave", "master": "m2", "slave": "s2"}
    )
    coordinator._pending_operations[op_id] = {
        "type": "set_slave",
        "master": "m2",
        "slave": "s2",
        "start_time": datetime.now(tz=UTC),
        "expected_state": "slave",
        "retry_count": 0,
        "last_check": None,
        "status": "pending",
        "data": {
            "type": "set_slave",
            "master": "m2",
            "slave": "s2",
            "params": full_params,
        },
        "request_callback": AsyncMock(),
    }
    with (
        patch.object(coordinator, "_execute_operation", AsyncMock(return_value=True)),
        patch.object(
            coordinator,
            "_poll_operation_status_with_callback",
            new_callable=AsyncMock,
        ),
        patch.object(hass, "async_create_task") as mock_ct,
    ):
        await coordinator.async_start_operation_processing(op_id)
    mock_ct.assert_called_once()


async def test_handle_operation_success_calls_cleanup(
    coordinator: HIVIGroupCoordinator,
) -> None:
    op_id = "set_slave_master_mx_slave_sx"
    start = datetime(2020, 1, 1, 12, 0, 0, tzinfo=UTC)
    end = datetime(2020, 1, 1, 12, 0, 2, tzinfo=UTC)

    class _DatetimeModule:
        UTC = UTC

        @staticmethod
        def now(tz=None):
            return end

    coordinator._pending_operations[op_id] = {
        "type": "set_slave",
        "master": "mx",
        "slave": "sx",
        "retry_count": 0,
        "start_time": start,
    }
    with (
        patch.object(coordinator, "_cleanup_operation", new_callable=AsyncMock) as mock_clean,
        patch(
            "homeassistant.components.hivi_speaker.group_coordinator.datetime",
            _DatetimeModule,
        ),
    ):
        await coordinator._handle_operation_success(op_id)
    mock_clean.assert_awaited_once_with(op_id)


async def test_handle_operation_timeout_calls_cleanup(
    coordinator: HIVIGroupCoordinator,
) -> None:
    op_id = "set_slave_master_my_slave_sy"
    coordinator._pending_operations[op_id] = {
        "type": "set_slave",
        "master": "my",
        "slave": "sy",
        "retry_count": 0,
        "start_time": datetime.now(tz=UTC),
    }
    with patch.object(coordinator, "_cleanup_operation", new_callable=AsyncMock) as mock_clean:
        await coordinator._handle_operation_timeout(op_id)
    mock_clean.assert_awaited_once_with(op_id)


async def test_async_start_operation_processing_callback_raises_triggers_failed(
    coordinator: HIVIGroupCoordinator,
) -> None:
    op_id = "op_cb_runtime"
    # First await is "executing"; except block awaits again with status "error" — must not re-raise.
    cb = AsyncMock(
        side_effect=[RuntimeError("executing callback boom"), None],
    )
    coordinator._pending_operations[op_id] = {
        "type": "set_slave",
        "master": "m",
        "slave": "s",
        "start_time": datetime.now(tz=UTC),
        "expected_state": "slave",
        "retry_count": 0,
        "data": {
            "type": "set_slave",
            "master": "m",
            "slave": "s",
            "params": {
                "slave_ip": "192.168.1.2",
                "ssid": "w",
                "wifi_channel": "6",
                "auth": "wpa2",
            },
        },
        "request_callback": cb,
    }
    with patch.object(coordinator, "_handle_operation_failed", new_callable=AsyncMock) as mock_fail:
        await coordinator.async_start_operation_processing(op_id)
    mock_fail.assert_awaited_once()
    err_calls = [c for c in cb.await_args_list if c.args[0].get("status") == "error"]
    assert err_calls


async def test_poll_operation_status_success_set_slave(
    coordinator: HIVIGroupCoordinator,
) -> None:
    op_id = "poll_set_ok"
    coordinator._pending_operations[op_id] = {
        "type": "set_slave",
        "slave": "slave-uuid",
        "start_time": _POLL_OP_START,
        "retry_count": 0,
        "data": {"params": {"master_ip": "192.168.1.1"}},
        "request_callback": AsyncMock(),
    }
    # Keep instant sleep: failure/exception paths use asyncio.sleep(poll_interval); real 2s*retries can hit pytest-timeout.
    with (
        _patch_group_coordinator_datetime_for_poll(),
        patch.object(coordinator, "_verify_operation_state", AsyncMock(return_value=True)),
        _patch_group_coordinator_asyncio_sleep(_gc_sleep_zero),
        patch.object(coordinator, "_handle_operation_success", new_callable=AsyncMock) as mock_ok,
    ):
        await coordinator._poll_operation_status_with_callback(op_id)
    mock_ok.assert_awaited_once_with(op_id)


async def test_poll_operation_status_remove_slave_sleeps_before_success(
    coordinator: HIVIGroupCoordinator,
) -> None:
    op_id = "poll_rm_ok"
    coordinator._pending_operations[op_id] = {
        "type": "remove_slave",
        "slave": "rm-uuid",
        "start_time": _POLL_OP_START,
        "retry_count": 0,
        "data": {"params": {"master_ip": "192.168.1.3"}},
        "request_callback": AsyncMock(),
    }
    recorded_delays: list[float] = []

    async def _track_sleep(delay: float = 0) -> None:
        recorded_delays.append(delay)
        await asyncio.sleep(0)

    with (
        _patch_group_coordinator_datetime_for_poll(),
        patch.object(coordinator, "_verify_operation_state", AsyncMock(return_value=True)),
        _patch_group_coordinator_asyncio_sleep(_track_sleep),
        patch.object(coordinator, "_handle_operation_success", new_callable=AsyncMock),
    ):
        await coordinator._poll_operation_status_with_callback(op_id)
    assert recorded_delays == [10]


async def test_poll_operation_status_polling_error_sleeps(
    coordinator: HIVIGroupCoordinator,
) -> None:
    op_id = "poll_err"
    coordinator._pending_operations[op_id] = {
        "type": "set_slave",
        "slave": "u",
        "start_time": _POLL_OP_START,
        "retry_count": 0,
        "data": {"params": {"master_ip": "192.168.1.1"}},
        "request_callback": AsyncMock(),
    }
    verify = AsyncMock(side_effect=[OSError("poll"), True])
    recorded_delays: list[float] = []

    async def _track_sleep(delay: float = 0) -> None:
        recorded_delays.append(delay)
        await asyncio.sleep(0)

    with (
        _patch_group_coordinator_datetime_for_poll(),
        patch.object(coordinator, "_verify_operation_state", verify),
        _patch_group_coordinator_asyncio_sleep(_track_sleep),
        patch.object(coordinator, "_handle_operation_success", new_callable=AsyncMock) as mock_ok,
    ):
        await coordinator._poll_operation_status_with_callback(op_id)
    assert coordinator._poll_interval in recorded_delays
    mock_ok.assert_awaited_once_with(op_id)


async def test_cleanup_operation_removes_pending_and_poll_task(
    hass: HomeAssistant,
    coordinator: HIVIGroupCoordinator,
) -> None:
    op_id = "op_clean"
    coordinator._pending_operations[op_id] = {"x": 1}
    coordinator._request_callbacks[op_id] = MagicMock()
    task = hass.async_create_task(asyncio.sleep(0))
    await asyncio.sleep(0)
    coordinator._poll_tasks[op_id] = task
    with _patch_group_coordinator_asyncio_sleep(_gc_sleep_zero):
        await coordinator._cleanup_operation(op_id)
    assert op_id not in coordinator._pending_operations
    assert op_id not in coordinator._request_callbacks
    assert op_id not in coordinator._poll_tasks


async def test_dispatcher_sync_group_operation_schedules_set_slave(
    hass: HomeAssistant,
) -> None:
    dm = MagicMock()
    ds = MagicMock()
    coord = HIVIGroupCoordinator(hass, dm, ds)
    with patch.object(EventBus, "async_listen"):
        await coord.async_start()
    try:
        with patch.object(coord, "async_set_slave_speaker", new_callable=AsyncMock) as mock_ass:
            async_dispatcher_send(
                hass,
                f"{DOMAIN}_sync_group_operation",
                {"type": "set_slave", "master": "ma", "slave": "sb"},
                None,
            )
            await hass.async_block_till_done()
        mock_ass.assert_awaited_once()
    finally:
        coord._poll_tasks.clear()
        await coord.async_stop()


def test_check_conflicts_passes_when_pending_disjoint(
    coordinator: HIVIGroupCoordinator,
) -> None:
    coordinator._pending_operations["o"] = {"master": "a", "slave": "b"}
    out = coordinator._check_conflicting_operations(
        {"type": "set_slave", "master": "c", "slave": "d"}
    )
    assert out["has_conflict"] is False
    assert out["conflict_type"] == "no_conflict"


def test_log_detailed_conflict_analysis_no_overlap(
    coordinator: HIVIGroupCoordinator,
) -> None:
    coordinator._pending_operations["p"] = {"master": "a", "slave": "b"}
    coordinator._log_detailed_conflict_analysis({"master": "c", "slave": "d"})


async def test_get_operation_status_includes_duration(
    coordinator: HIVIGroupCoordinator,
) -> None:
    st = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
    en = datetime(2020, 1, 1, 0, 0, 10, tzinfo=UTC)
    coordinator._pending_operations["op"] = {
        "type": "set_slave",
        "master": "m",
        "slave": "s",
        "start_time": st,
        "end_time": en,
        "retry_count": 0,
    }
    out = await coordinator.get_operation_status("op")
    assert out is not None
    assert out["duration"] == pytest.approx(10.0)


async def test_get_all_operations(coordinator: HIVIGroupCoordinator) -> None:
    st = datetime(2020, 1, 1, 0, 0, 0, tzinfo=UTC)
    en = datetime(2020, 1, 1, 0, 0, 3, tzinfo=UTC)
    coordinator._pending_operations["a"] = {
        "type": "set_slave",
        "master": "m",
        "slave": "s",
        "start_time": st,
        "end_time": en,
    }
    out = await coordinator.get_all_operations()
    assert "a" in out
    assert out["a"]["duration"] == pytest.approx(3.0)


async def test_cancel_operation_unknown_returns_false(
    coordinator: HIVIGroupCoordinator,
) -> None:
    assert await coordinator.cancel_operation("missing") is False


async def test_cancel_operation_invokes_cleanup(
    coordinator: HIVIGroupCoordinator,
) -> None:
    coordinator._pending_operations["c"] = {
        "master": "m",
        "slave": "s",
        "type": "set_slave",
        "retry_count": 0,
    }
    with patch.object(coordinator, "_cleanup_operation", new_callable=AsyncMock) as mock_c:
        ok = await coordinator.cancel_operation("c")
    assert ok is True
    mock_c.assert_awaited_once_with("c")


def test_handle_operation_started_logs(
    coordinator: HIVIGroupCoordinator,
) -> None:
    ev = MagicMock()
    ev.data = {"operation_id": "oid"}
    coordinator._handle_operation_started(ev)


def test_handle_device_updated_logs_when_related(
    coordinator: HIVIGroupCoordinator,
) -> None:
    coordinator._pending_operations["x"] = {"master": "m1", "slave": "s1"}
    ev = MagicMock()
    ev.data = {"speaker_device_id": "m1"}
    coordinator._handle_device_updated(ev)


async def test_poll_operation_status_warns_when_operation_missing(
    coordinator: HIVIGroupCoordinator,
) -> None:
    await coordinator._poll_operation_status("no-such-op")


async def test_legacy_poll_operation_status_success(
    coordinator: HIVIGroupCoordinator,
) -> None:
    op_id = "leg_ok"
    coordinator._pending_operations[op_id] = {
        "type": "set_slave",
        "slave": "s",
        "start_time": _POLL_OP_START,
        "retry_count": 0,
        "data": {"params": {"master_ip": "192.168.1.1"}},
    }
    with (
        _patch_group_coordinator_datetime_for_poll(),
        _patch_group_coordinator_asyncio_sleep(_gc_sleep_zero),
        patch.object(coordinator, "_verify_operation_state", AsyncMock(return_value=True)),
        patch.object(coordinator, "_handle_operation_success", new_callable=AsyncMock),
    ):
        await coordinator._poll_operation_status(op_id)


async def test_verify_operation_state_false_without_master_ip(
    coordinator: HIVIGroupCoordinator,
) -> None:
    op = {"type": "set_slave", "slave": "u", "data": {"params": {}}}
    assert await coordinator._verify_operation_state(op) is False


async def test_check_actual_state_timeout_returns_unknown(
    coordinator: HIVIGroupCoordinator,
) -> None:
    mc = MagicMock()
    mc.state.async_get_slave_devices = AsyncMock(side_effect=TimeoutError)
    assert await coordinator._check_actual_state(mc, "u") == "unknown"


async def test_check_actual_state_oserror_returns_unknown(
    coordinator: HIVIGroupCoordinator,
) -> None:
    mc = MagicMock()
    mc.state.async_get_slave_devices = AsyncMock(side_effect=OSError)
    assert await coordinator._check_actual_state(mc, "u") == "unknown"


async def test_check_actual_state_slave_standalone_unknown(
    coordinator: HIVIGroupCoordinator,
) -> None:
    mc = MagicMock()
    mc.state.async_get_slave_devices = AsyncMock(return_value={"sid": {}})
    assert await coordinator._check_actual_state(mc, "sid") == "slave"
    assert await coordinator._check_actual_state(mc, "other") == "standalone"
    mc.state.async_get_slave_devices = AsyncMock(return_value=None)
    assert await coordinator._check_actual_state(mc, "sid") == "unknown"


async def test_handle_operation_failed_noop_when_operation_missing(
    coordinator: HIVIGroupCoordinator,
) -> None:
    await coordinator._handle_operation_failed("gone", "reason")


async def test_handle_operation_success_noop_when_operation_missing(
    coordinator: HIVIGroupCoordinator,
) -> None:
    await coordinator._handle_operation_success("gone")


async def test_handle_operation_timeout_noop_when_operation_missing(
    coordinator: HIVIGroupCoordinator,
) -> None:
    await coordinator._handle_operation_timeout("gone")

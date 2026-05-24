"""Phase 9 tests for :class:`hass_client.sandbox.SandboxRuntime` shutdown.

The runtime registers ``sandbox_v2/shutdown`` once its channel is up.
These tests exercise:

* the shutdown handler unloads loaded entries via
  ``config_entries.async_unload`` and ships a JSON-safe
  ``restore_state`` snapshot back in the reply (so main can persist it);
* once the handler replies, the runtime exits cleanly so ``run()``
  returns 0 without main needing to escalate to SIGTERM;
* ``run()`` warm-loads ``core.restore_state`` from main before the
  channel starts, so a fresh RestoreEntity sees the previous run's
  state via ``async_get_last_state``.
"""

import asyncio
from typing import Any

from hass_client.channel import Channel
from hass_client.protocol import MSG_SHUTDOWN, MSG_STORE_LOAD, MSG_STORE_SAVE
from hass_client.sandbox import SandboxRuntime
import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.core import State
from homeassistant.helpers import restore_state, storage as _storage
from homeassistant.util import dt as dt_util


class _LoopbackWriter:
    def __init__(self, target: asyncio.StreamReader) -> None:
        self._target = target

    def write(self, data: bytes) -> None:
        self._target.feed_data(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self._target.feed_eof()

    async def wait_closed(self) -> None:
        return None


def _make_channel_pair() -> tuple[Channel, Channel]:
    """Two channels joined by an in-memory bytes transport."""
    reader_a = asyncio.StreamReader()
    reader_b = asyncio.StreamReader()
    return (
        Channel(reader_a, _LoopbackWriter(reader_b), name="main"),  # type: ignore[arg-type]
        Channel(reader_b, _LoopbackWriter(reader_a), name="sandbox"),  # type: ignore[arg-type]
    )


@pytest.fixture(name="runtime_pair")
async def _runtime_pair_fixture():
    """SandboxRuntime + main-side channel joined by an in-memory pair.

    Yields ``(runtime, main_channel, run_task)``. The runtime owns the
    sandbox side; its channel factory returns the sandbox half of the
    pair. The fixture cancels and awaits the task on teardown.
    """
    main_channel, sandbox_channel = _make_channel_pair()

    async def _channel_factory() -> Channel:
        return sandbox_channel

    runtime = SandboxRuntime(
        url="ws://x",
        token="t",
        group="custom",
        channel_factory=_channel_factory,
    )

    main_channel.start()
    task = asyncio.create_task(runtime.run())

    # ``started`` flips True before the warm-load — wait until handlers
    # are actually registered before we let the test issue calls.
    loop = asyncio.get_event_loop()
    deadline = loop.time() + 2.0
    while not runtime.started and loop.time() < deadline:
        await asyncio.sleep(0.01)
    assert runtime.started
    await runtime.wait_until_ready(timeout=2.0)

    try:
        yield runtime, main_channel, task
    finally:
        if not task.done():
            runtime.request_shutdown()
            try:
                await asyncio.wait_for(task, timeout=2.0)
            except (TimeoutError, Exception):  # noqa: BLE001
                task.cancel()
        await main_channel.close()


async def test_shutdown_handler_returns_summary_and_exits(
    runtime_pair: tuple[SandboxRuntime, Channel, asyncio.Task[int]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``sandbox_v2/shutdown`` replies with a summary and the runtime exits 0."""
    _runtime, main_channel, task = runtime_pair

    result = await asyncio.wait_for(
        main_channel.call(MSG_SHUTDOWN, None), timeout=5.0
    )

    assert result["ok"] is True
    assert result["unloaded"] == 0
    # No entries → no live RestoreEntity → restore_state stays None.
    assert result["restore_state"] is None

    # The runtime sets its shutdown event right after replying — wait for
    # ``run()`` to return on its own; no SIGTERM should be needed.
    exit_code = await asyncio.wait_for(task, timeout=5.0)
    assert exit_code == 0
    capsys.readouterr()


async def test_shutdown_returns_restore_state_payload(
    runtime_pair: tuple[SandboxRuntime, Channel, asyncio.Task[int]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The shutdown handler returns a JSON-safe restore-state snapshot.

    Restore state ships back in the reply (not via ``RemoteStore``)
    because the channel reader task is busy dispatching the shutdown
    handler — a re-entrant ``store_save`` call would deadlock. Main is
    responsible for persisting the payload before SIGTERM.
    """
    runtime, main_channel, _task = runtime_pair

    # Seed an in-memory restore-state entry so the snapshot has data.
    hass = runtime._flow_runner.hass  # noqa: SLF001
    restore_data = restore_state.async_get(hass)
    restore_data.last_states["sensor.demo"] = restore_state.StoredState(
        state=State("sensor.demo", "42"),
        extra_data=None,
        last_seen=dt_util.utcnow(),
    )

    reply = await asyncio.wait_for(
        main_channel.call(MSG_SHUTDOWN, None), timeout=5.0
    )

    assert reply["ok"] is True
    restore_payload = reply["restore_state"]
    assert isinstance(restore_payload, dict)
    assert restore_payload["version"] == restore_state.STORAGE_VERSION
    assert restore_payload["key"] == restore_state.STORAGE_KEY
    entity_ids = [item["state"]["entity_id"] for item in restore_payload["data"]]
    assert "sensor.demo" in entity_ids
    capsys.readouterr()


async def test_shutdown_fires_final_write_event(
    runtime_pair: tuple[SandboxRuntime, Channel, asyncio.Task[int]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Phase 12: the shutdown handler fires EVENT_HOMEASSISTANT_FINAL_WRITE.

    Concurrent channel dispatcher means the FINAL_WRITE fire-and-drain
    inside the shutdown handler no longer deadlocks against re-entrant
    ``RemoteStore`` writes triggered by listeners on the event.
    """
    runtime, main_channel, _task = runtime_pair
    hass = runtime._flow_runner.hass  # noqa: SLF001

    fired: list[Any] = []

    def _on_final_write(event: Any) -> None:
        fired.append(event)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_FINAL_WRITE, _on_final_write)

    reply = await asyncio.wait_for(
        main_channel.call(MSG_SHUTDOWN, None), timeout=5.0
    )
    assert reply["ok"] is True
    assert len(fired) == 1
    capsys.readouterr()


async def test_shutdown_flushes_pending_delay_save(
    runtime_pair: tuple[SandboxRuntime, Channel, asyncio.Task[int]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Phase 12: ``async_delay_save`` writes flush through ``RemoteStore``.

    Without the concurrent channel dispatcher this would deadlock: the
    Store's FINAL_WRITE listener would re-enter the same channel reader
    that is dispatching the shutdown handler. With Phase 12 the inner
    ``store_save`` lands on the main-side handler while the shutdown
    handler is still running.
    """
    runtime, main_channel, _task = runtime_pair
    hass = runtime._flow_runner.hass  # noqa: SLF001

    saves: list[dict[str, Any]] = []

    async def _on_store_save(payload: dict[str, Any]) -> None:
        saves.append(payload)

    main_channel.register(MSG_STORE_SAVE, _on_store_save)

    # ``install_remote_store`` already patched ``Store`` during ``run()``,
    # so resolving ``Store`` via the module attribute returns the
    # ``RemoteStore`` subclass that routes writes at our main channel.
    store = _storage.Store(hass, 1, "phase12_test")
    store.async_delay_save(lambda: {"pending": True}, 3600)

    reply = await asyncio.wait_for(
        main_channel.call(MSG_SHUTDOWN, None), timeout=5.0
    )
    assert reply["ok"] is True

    save_keys = [save["key"] for save in saves]
    assert "phase12_test" in save_keys
    saved = next(save for save in saves if save["key"] == "phase12_test")
    assert saved["data"]["data"] == {"pending": True}
    capsys.readouterr()


async def test_run_warm_loads_restore_state_on_startup(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``run()`` issues a ``store_load`` for ``core.restore_state`` before handlers."""
    main_channel, sandbox_channel = _make_channel_pair()
    load_calls: list[str] = []

    async def _on_load(payload: dict[str, Any]) -> dict[str, Any] | None:
        load_calls.append(payload["key"])
        return None

    main_channel.register(MSG_STORE_LOAD, _on_load)
    main_channel.start()

    async def _channel_factory() -> Channel:
        return sandbox_channel

    runtime = SandboxRuntime(
        url="ws://x",
        token="t",
        group="custom",
        channel_factory=_channel_factory,
    )

    task = asyncio.create_task(runtime.run())
    try:
        # Wait for the runtime to issue the warm-load RPC.
        loop = asyncio.get_event_loop()
        deadline = loop.time() + 2.0
        while restore_state.STORAGE_KEY not in load_calls and loop.time() < deadline:
            await asyncio.sleep(0.01)
        assert restore_state.STORAGE_KEY in load_calls
    finally:
        runtime.request_shutdown()
        await asyncio.wait_for(task, timeout=2.0)
        await main_channel.close()
        await sandbox_channel.close()
    capsys.readouterr()

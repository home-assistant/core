"""Tests for the ``current_sandbox`` contextvar store routing.

These exercise the routing primitive that replaced the former
module-level ``Store`` rebinding (the deleted ``remote_store`` module):

* Most tests drive ``Store``'s public API through the contextvar branch
  using an in-memory ``_FakeBridge`` set on ``current_sandbox`` directly —
  no channel. They cover load/unwrap, missing keys, migration, the
  no-sandbox disk path, the ``restore_state`` warm-load, contextvar task
  inheritance, and (the A2 guard) the ``async_delay_save`` / FINAL_WRITE
  flush.
* The final test exercises the concrete :class:`ChannelSandboxBridge` over
  an in-memory channel pair, covering the wire mapping of
  ``sandbox_bridge.py`` directly — the coverage ``test_remote_store.py``
  used to provide transitively before A2 deleted it.
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
import tempfile
from typing import Any

from hass_client.channel import Channel
from hass_client.flow_runner import FlowRunner
from hass_client.sandbox_bridge import ChannelSandboxBridge
import pytest

from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import restore_state, storage as _storage
from homeassistant.helpers.sandbox_context import current_sandbox


class _FakeBridge:
    """In-memory ``SandboxBridge`` for exercising the contextvar path.

    ``loaded`` maps a key to the *wrapped* envelope the bridge hands back
    (matching the real bridge contract); ``saved`` records the wrapped
    envelopes pushed back through ``async_store_save``.
    """

    def __init__(self) -> None:
        self.loaded: dict[str, Any] = {}
        self.load_keys: list[str] = []
        self.saved: dict[str, Any] = {}
        self.removed: list[str] = []

    async def async_store_load(self, key: str) -> Any:
        self.load_keys.append(key)
        return self.loaded.get(key)

    async def async_store_save(self, key: str, data: Any) -> None:
        # Mirror ``ChannelSandboxBridge``: resolve a deferred ``data_func``
        # (handed down by ``async_delay_save``) into a concrete ``data`` key
        # before recording the envelope.
        if "data_func" in data:
            data["data"] = data.pop("data_func")()
        self.saved[key] = data

    async def async_store_remove(self, key: str) -> None:
        self.removed.append(key)


def _wrap(version: int, minor_version: int, key: str, data: Any) -> dict[str, Any]:
    """Build a storage envelope the way ``Store.async_save`` does."""
    return {
        "version": version,
        "minor_version": minor_version,
        "key": key,
        "data": data,
    }


@pytest.fixture(name="hass_runtime")
async def _hass_runtime_fixture() -> AsyncGenerator[HomeAssistant]:
    """A bare sandbox HA, like the runtime builds via ``FlowRunner.create``."""
    with tempfile.TemporaryDirectory(prefix="sandbox_v2_bridge_") as tmp:
        flow_runner = await FlowRunner.create(config_dir=tmp)
        try:
            yield flow_runner.hass
        finally:
            await flow_runner.async_stop()


@pytest.fixture(name="bridge")
def _bridge_fixture() -> Generator[_FakeBridge]:
    """Set a fake bridge on ``current_sandbox`` and reset it afterwards."""
    bridge = _FakeBridge()
    token = current_sandbox.set(bridge)
    try:
        yield bridge
    finally:
        current_sandbox.reset(token)


async def test_load_routes_to_bridge_and_unwraps(
    hass_runtime: HomeAssistant,
    bridge: _FakeBridge,
) -> None:
    """``Store.async_load`` reaches the bridge by key and returns unwrapped data."""
    bridge.loaded["demo"] = _wrap(1, 1, "demo", {"hello": "world"})

    store = _storage.Store(hass_runtime, 1, "demo")
    loaded = await store.async_load()

    assert bridge.load_keys == ["demo"]
    assert loaded == {"hello": "world"}


async def test_load_returns_none_when_bridge_has_no_data(
    hass_runtime: HomeAssistant,
    bridge: _FakeBridge,
) -> None:
    """A missing key reads back as ``None`` (matching ``Store`` semantics)."""
    store = _storage.Store(hass_runtime, 1, "missing")
    assert await store.async_load() is None
    assert bridge.load_keys == ["missing"]


@pytest.mark.parametrize(
    "migrate_params",
    [
        pytest.param(2, id="2-arg-migrate-func"),
        pytest.param(3, id="3-arg-migrate-func"),
    ],
)
async def test_migration_runs_through_bridge(
    hass_runtime: HomeAssistant,
    bridge: _FakeBridge,
    migrate_params: int,
) -> None:
    """A version mismatch runs the migrate func and saves back via the bridge.

    Mirrors ``test_remote_store.test_migration_runs_when_version_differs``
    but through the contextvar path, and across both ``_async_migrate_func``
    arities — the post-migration ``async_save`` must recurse back through the
    bridge.
    """
    bridge.loaded["migrating"] = _wrap(1, 1, "migrating", {"shape": "old"})

    if migrate_params == 2:

        class _MigratingStore(_storage.Store):
            async def _async_migrate_func(
                self,
                old_major_version: int,
                old_data: dict[str, Any],
            ) -> dict[str, Any]:
                return {"shape": "new", "was": old_data["shape"]}
    else:

        class _MigratingStore(_storage.Store):
            async def _async_migrate_func(
                self,
                old_major_version: int,
                old_minor_version: int,
                old_data: dict[str, Any],
            ) -> dict[str, Any]:
                return {"shape": "new", "was": old_data["shape"]}

    store = _MigratingStore(hass_runtime, 2, "migrating")
    loaded = await store.async_load()

    assert loaded == {"shape": "new", "was": "old"}
    # Migration recursed back through the bridge to persist the new shape.
    assert bridge.saved["migrating"]["version"] == 2
    assert bridge.saved["migrating"]["data"] == {"shape": "new", "was": "old"}


async def test_no_sandbox_round_trip_uses_local_disk(
    hass_runtime: HomeAssistant,
) -> None:
    """With ``current_sandbox`` unset, save/load hit local disk as before.

    Regression guard for the no-sandbox path: the contextvar branch must be
    a no-op when nothing is set.
    """
    assert current_sandbox.get() is None

    store = _storage.Store(hass_runtime, 1, "local_only")
    await store.async_save({"on": "disk"})

    other = _storage.Store(hass_runtime, 1, "local_only")
    assert await other.async_load() == {"on": "disk"}


async def test_restore_state_warm_load_without_workaround(
    hass_runtime: HomeAssistant,
    bridge: _FakeBridge,
) -> None:
    """``RestoreStateData`` warm-load reaches the bridge with no store swap.

    The smoking gun that the contextvar fix subsumes the explicit
    ``data.store`` swap A2 deleted from ``sandbox.py``: a vanilla
    ``RestoreStateData`` (which captured the original ``Store`` at module
    import) routes its ``async_load`` to the bridge purely because the
    contextvar is set — no explicit store replacement.
    """
    data = restore_state.RestoreStateData(hass_runtime)
    await data.async_load()

    assert restore_state.STORAGE_KEY in bridge.load_keys
    assert data.last_states == {}


async def test_contextvar_inherits_across_create_task(
    hass_runtime: HomeAssistant,
) -> None:
    """A task spawned after ``set`` inherits the contextvar and reaches the bridge.

    Guards against a future refactor that creates a task *before* the
    runtime sets ``current_sandbox`` — that task would not inherit the
    bridge and would silently route to local disk.
    """
    bridge = _FakeBridge()
    bridge.loaded["in_task"] = _wrap(1, 1, "in_task", {"from": "task"})
    token = current_sandbox.set(bridge)

    async def _load_in_task() -> Any:
        store = _storage.Store(hass_runtime, 1, "in_task")
        return await store.async_load()

    try:
        result = await asyncio.create_task(_load_in_task())
    finally:
        current_sandbox.reset(token)

    assert bridge.load_keys == ["in_task"]
    assert result == {"from": "task"}


async def test_delayed_save_flushes_through_bridge(
    hass_runtime: HomeAssistant,
    bridge: _FakeBridge,
) -> None:
    """``async_delay_save`` + the FINAL_WRITE flush route through the bridge.

    The A2 regression guard. ``async_delay_save`` and the
    EVENT_HOMEASSISTANT_FINAL_WRITE flush bypass ``async_save`` entirely —
    they funnel through ``_async_handle_write_data`` -> ``_async_write_data``.
    The contextvar branch must live at ``_async_write_data`` (not only
    ``async_save``) or these writes would silently land on the sandbox's
    local disk instead of reaching main. The Phase 8 store subclass
    overrode ``_async_write_data`` and masked this; deleting it surfaced the
    gap.
    """
    store = _storage.Store(hass_runtime, 1, "delayed")
    store.async_delay_save(lambda: {"foo": "bar"}, delay=0)

    # The FINAL_WRITE listener (armed by async_delay_save) flushes the
    # pending envelope; whichever of it / the delay timer fires first wins
    # the write lock, the other is a no-op. Either path is _async_write_data.
    hass_runtime.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
    await hass_runtime.async_block_till_done()

    assert "delayed" in bridge.saved
    assert bridge.saved["delayed"]["key"] == "delayed"
    assert bridge.saved["delayed"]["data"] == {"foo": "bar"}


# --- ChannelSandboxBridge wire mapping (the new sandbox_bridge.py file) ---


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
    reader_a = asyncio.StreamReader()
    reader_b = asyncio.StreamReader()
    return (
        Channel(reader_a, _LoopbackWriter(reader_b), name="main"),  # type: ignore[arg-type]
        Channel(reader_b, _LoopbackWriter(reader_a), name="sandbox"),  # type: ignore[arg-type]
    )


async def test_channel_bridge_maps_store_rpcs() -> None:
    """``ChannelSandboxBridge`` maps each method onto its MSG_STORE_* RPC."""
    main, sandbox = _make_channel_pair()
    saved: dict[str, Any] = {}
    removed: list[str] = []

    async def _on_save(payload: dict[str, Any]) -> dict[str, bool]:
        saved[payload["key"]] = payload["data"]
        return {"ok": True}

    async def _on_load(payload: dict[str, Any]) -> dict[str, Any] | None:
        return saved.get(payload["key"])

    async def _on_remove(payload: dict[str, Any]) -> dict[str, bool]:
        removed.append(payload["key"])
        return {"ok": True}

    main.register("sandbox_v2/store_save", _on_save)
    main.register("sandbox_v2/store_load", _on_load)
    main.register("sandbox_v2/store_remove", _on_remove)
    main.start()
    sandbox.start()

    try:
        bridge = ChannelSandboxBridge(sandbox)
        wrapped = _wrap(1, 1, "wire", {"k": "v"})
        await bridge.async_store_save("wire", dict(wrapped))

        assert saved["wire"]["data"] == {"k": "v"}
        assert await bridge.async_store_load("wire") == saved["wire"]

        await bridge.async_store_remove("wire")
        assert removed == ["wire"]
    finally:
        await main.close()
        await sandbox.close()

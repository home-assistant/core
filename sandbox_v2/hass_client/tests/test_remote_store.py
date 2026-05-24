"""Phase 8 tests for :class:`hass_client.remote_store.RemoteStore`.

Each test runs the patched-in ``Store`` against an in-memory channel
pair that pretends to be main. We assert RemoteStore proxies all three
operations correctly, runs migration when versions differ, and that the
install/uninstall pair restores ``homeassistant.helpers.storage.Store``
to its original value.
"""

import asyncio
import tempfile
from typing import Any

from hass_client.channel import Channel
from hass_client.flow_runner import FlowRunner
from hass_client.remote_store import RemoteStore, install_remote_store
import pytest

from homeassistant.helpers import storage as _storage


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


@pytest.fixture(name="channels")
async def _channels_fixture() -> tuple[Channel, Channel]:
    main, sandbox = _make_channel_pair()
    yield main, sandbox
    await main.close()
    await sandbox.close()


@pytest.fixture(name="hass_runtime")
async def _hass_runtime_fixture():
    with tempfile.TemporaryDirectory(prefix="sandbox_v2_remote_store_") as tmp:
        flow_runner = await FlowRunner.create(config_dir=tmp)
        try:
            yield flow_runner.hass
        finally:
            await flow_runner.async_stop()


@pytest.fixture(name="installed_store")
def _installed_store_fixture(channels: tuple[Channel, Channel]):
    """Install RemoteStore on the channel pair and tear it down afterwards."""
    _main, sandbox = channels
    uninstall = install_remote_store(sandbox)
    yield sandbox
    uninstall()


async def test_install_replaces_store_symbol(channels: tuple[Channel, Channel]) -> None:
    """``install_remote_store`` patches ``storage.Store`` and uninstall restores it."""
    _main, sandbox = channels
    original = _storage.Store
    uninstall = install_remote_store(sandbox)
    try:
        assert _storage.Store is RemoteStore
    finally:
        uninstall()
    assert _storage.Store is original
    assert RemoteStore._channel is None  # noqa: SLF001


async def test_save_then_load_round_trip(
    channels: tuple[Channel, Channel],
    hass_runtime: Any,
    installed_store: Channel,
) -> None:
    """A round-trip through a fake main returns the saved data."""
    main, _sandbox = channels
    saved: dict[str, Any] = {}

    async def _on_save(payload: dict[str, Any]) -> dict[str, bool]:
        saved[payload["key"]] = payload["data"]
        return {"ok": True}

    async def _on_load(payload: dict[str, Any]) -> dict[str, Any] | None:
        return saved.get(payload["key"])

    main.register("sandbox_v2/store_save", _on_save)
    main.register("sandbox_v2/store_load", _on_load)
    main.start()
    installed_store.start()

    store = _storage.Store(hass_runtime, 1, "phase8_demo")
    await store.async_save({"hello": "world"})

    assert saved["phase8_demo"]["data"] == {"hello": "world"}
    assert saved["phase8_demo"]["version"] == 1

    # Fresh Store with no in-memory data must round-trip through main.
    other = _storage.Store(hass_runtime, 1, "phase8_demo")
    loaded = await other.async_load()
    assert loaded == {"hello": "world"}


async def test_load_returns_none_when_main_has_no_data(
    channels: tuple[Channel, Channel],
    hass_runtime: Any,
    installed_store: Channel,
) -> None:
    """A missing key reads back as ``None`` (matching ``Store`` semantics)."""
    main, _sandbox = channels

    async def _on_load(_payload: dict[str, Any]) -> None:
        return None

    main.register("sandbox_v2/store_load", _on_load)
    main.start()
    installed_store.start()

    store = _storage.Store(hass_runtime, 1, "missing_key")
    assert await store.async_load() is None


async def test_remove_proxies_to_main(
    channels: tuple[Channel, Channel],
    hass_runtime: Any,
    installed_store: Channel,
) -> None:
    """``async_remove`` fires a ``sandbox_v2/store_remove`` RPC."""
    main, _sandbox = channels
    removed: list[str] = []

    async def _on_remove(payload: dict[str, Any]) -> dict[str, bool]:
        removed.append(payload["key"])
        return {"ok": True}

    main.register("sandbox_v2/store_remove", _on_remove)
    main.start()
    installed_store.start()

    store = _storage.Store(hass_runtime, 1, "drop_me")
    await store.async_remove()

    assert removed == ["drop_me"]


async def test_migration_runs_when_version_differs(
    channels: tuple[Channel, Channel],
    hass_runtime: Any,
    installed_store: Channel,
) -> None:
    """A wrapped v1 payload prompts the subclass's migrate_func + a write back."""
    main, _sandbox = channels
    saved: dict[str, Any] = {}

    async def _on_save(payload: dict[str, Any]) -> dict[str, bool]:
        saved[payload["key"]] = payload["data"]
        return {"ok": True}

    async def _on_load(_payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "version": 1,
            "minor_version": 1,
            "key": "phase8_migrating",
            "data": {"shape": "old"},
        }

    main.register("sandbox_v2/store_save", _on_save)
    main.register("sandbox_v2/store_load", _on_load)
    main.start()
    installed_store.start()

    class _MigratingStore(_storage.Store):
        async def _async_migrate_func(
            self,
            old_major_version: int,
            old_minor_version: int,
            old_data: dict[str, Any],
        ) -> dict[str, Any]:
            return {"shape": "new", "was": old_data["shape"]}

    store = _MigratingStore(hass_runtime, 2, "phase8_migrating")
    loaded = await store.async_load()
    assert loaded == {"shape": "new", "was": "old"}
    # Migration also wrote the post-migration shape back to main.
    assert saved["phase8_migrating"]["version"] == 2
    assert saved["phase8_migrating"]["data"] == {"shape": "new", "was": "old"}


async def test_load_with_channel_uninstalled_returns_none(
    channels: tuple[Channel, Channel],
    hass_runtime: Any,
) -> None:
    """A RemoteStore without an installed channel doesn't deadlock."""
    # Don't install — RemoteStore._channel stays None.
    main, sandbox = channels
    main.start()
    sandbox.start()
    # Manually construct a RemoteStore (the patched Store path is what the
    # install fixture exercises; this case is the diagnostic-only path).
    store = RemoteStore(hass_runtime, 1, "orphan")
    assert await store.async_load() is None

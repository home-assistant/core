"""Tests for the main-side Store handlers on :class:`SandboxBridge`.

We exercise the three ``sandbox/store_*`` handlers via the in-memory
channel pair, with the bridge wired against the real ``hass`` config
directory so we can also verify the on-disk layout.

Coverage:

* a save lands at ``<config>/.storage/sandbox/<group>/<key>``;
* a subsequent load round-trips the same payload;
* a load for a missing key returns ``None``;
* path-traversal attempts (``..`` / slashes) are rejected;
* two bridges with different groups never collide on the same key
  (scope isolation by construction).
* a "sandbox restart" simulated by tearing the bridge down and creating
  a fresh one with a new channel still reads the previously-saved data.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from homeassistant.components.sandbox._proto import sandbox_pb2 as pb
from homeassistant.components.sandbox.bridge import (
    _STORE_MAX_KEY_LENGTH,
    _STORE_MAX_VALUE_BYTES,
    SandboxBridge,
)
from homeassistant.components.sandbox.channel import Channel, ChannelRemoteError
from homeassistant.components.sandbox.messages import decode_json_dict, encode_json
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import STORAGE_DIR

from ._helpers import make_channel_pair


async def _wire(
    hass: HomeAssistant, group: str = "built-in"
) -> tuple[SandboxBridge, Channel, Channel]:
    """Build a bridge connected to an in-memory channel pair."""
    main_channel, sandbox_channel = make_channel_pair(name_a="main", name_b="sandbox")
    bridge = SandboxBridge(hass, group=group, channel=main_channel)
    main_channel.start()
    sandbox_channel.start()
    return bridge, main_channel, sandbox_channel


def _store_path(hass: HomeAssistant, group: str, key: str) -> Path:
    return Path(hass.config.path(STORAGE_DIR, "sandbox", group, key))


async def test_store_save_writes_to_namespaced_path(hass: HomeAssistant) -> None:
    """A save lands at ``.storage/sandbox/<group>/<key>`` on main."""
    _bridge, main_channel, sandbox_channel = await _wire(hass, group="built-in")
    wrapped = {
        "version": 1,
        "minor_version": 1,
        "key": "demo_key",
        "data": {"hello": "world"},
    }
    save = pb.StoreSave(key="demo_key")
    save.data = encode_json(wrapped)
    try:
        result = await sandbox_channel.call("sandbox/store_save", save)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert result.ok
    path = _store_path(hass, "built-in", "demo_key")
    assert path.is_file()
    # The file holds the wrapped Store payload verbatim.
    assert json.loads(path.read_text(encoding="utf-8")) == wrapped


async def test_store_load_returns_saved_payload(hass: HomeAssistant) -> None:
    """A save followed by a load round-trips the wrapped dict."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)
    wrapped = {
        "version": 2,
        "minor_version": 3,
        "key": "demo_key",
        "data": {"counter": 42},
    }
    save = pb.StoreSave(key="demo_key")
    save.data = encode_json(wrapped)
    try:
        await sandbox_channel.call("sandbox/store_save", save)
        loaded = await sandbox_channel.call(
            "sandbox/store_load", pb.StoreLoad(key="demo_key")
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert decode_json_dict(loaded.data) == wrapped


async def test_store_load_missing_key_returns_none(hass: HomeAssistant) -> None:
    """An unknown key reads back as ``None``."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)
    try:
        loaded = await sandbox_channel.call(
            "sandbox/store_load", pb.StoreLoad(key="never_saved")
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    # proto: a missing key returns a StoreLoadResult with no `data` field set.
    assert not loaded.HasField("data")


async def test_store_remove_unlinks_file(hass: HomeAssistant) -> None:
    """``store_remove`` removes the on-disk file."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)
    save = pb.StoreSave(key="to_remove")
    save.data = encode_json(
        {
            "version": 1,
            "minor_version": 1,
            "key": "to_remove",
            "data": {"x": 1},
        }
    )
    try:
        await sandbox_channel.call("sandbox/store_save", save)
        path = _store_path(hass, "built-in", "to_remove")
        assert path.is_file()

        result = await sandbox_channel.call(
            "sandbox/store_remove", pb.StoreRemove(key="to_remove")
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert result.ok
    assert not _store_path(hass, "built-in", "to_remove").exists()


async def test_store_remove_missing_key_is_noop(hass: HomeAssistant) -> None:
    """``store_remove`` on a missing key is a successful no-op."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)
    try:
        result = await sandbox_channel.call(
            "sandbox/store_remove", pb.StoreRemove(key="phantom")
        )
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert result.ok


@pytest.mark.parametrize(
    "bad_key",
    [
        "../escape",
        "foo/bar",
        "foo\\bar",
        "..",
        ".",
    ],
)
async def test_store_rejects_path_traversal(hass: HomeAssistant, bad_key: str) -> None:
    """Path-traversal keys are rejected before any file IO runs."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)
    try:
        with pytest.raises(ChannelRemoteError):
            await sandbox_channel.call("sandbox/store_load", pb.StoreLoad(key=bad_key))
    finally:
        await main_channel.close()
        await sandbox_channel.close()


async def test_store_rejects_missing_key(hass: HomeAssistant) -> None:
    """A payload without a 'key' string is rejected."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)
    try:
        with pytest.raises(ChannelRemoteError):
            await sandbox_channel.call("sandbox/store_load", pb.StoreLoad(key=""))
    finally:
        await main_channel.close()
        await sandbox_channel.close()


async def test_store_rejects_overlong_key(hass: HomeAssistant) -> None:
    """A key past the length cap is rejected before any file IO."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)
    try:
        with pytest.raises(ChannelRemoteError, match="too long"):
            await sandbox_channel.call(
                "sandbox/store_save",
                pb.StoreSave(key="k" * (_STORE_MAX_KEY_LENGTH + 1)),
            )
    finally:
        await main_channel.close()
        await sandbox_channel.close()


async def test_store_rejects_oversized_value(hass: HomeAssistant) -> None:
    """A value past the per-key byte cap is rejected, nothing hits disk."""
    _bridge, main_channel, sandbox_channel = await _wire(hass)
    oversized = "x" * (_STORE_MAX_VALUE_BYTES + 1)
    save = pb.StoreSave(key="too_big")
    save.data = encode_json(
        {
            "version": 1,
            "minor_version": 1,
            "key": "too_big",
            "data": {"blob": oversized},
        }
    )
    try:
        with pytest.raises(ChannelRemoteError, match="too large"):
            await sandbox_channel.call("sandbox/store_save", save)
    finally:
        await main_channel.close()
        await sandbox_channel.close()

    assert not _store_path(hass, "built-in", "too_big").exists()


async def test_store_groups_are_isolated(hass: HomeAssistant) -> None:
    """Two bridges with different groups never share a key namespace."""
    _bridge_builtin, main_a, sandbox_a = await _wire(hass, group="built-in")
    _bridge_custom, main_b, sandbox_b = await _wire(hass, group="custom")
    wrapped: dict[str, Any] = {
        "version": 1,
        "minor_version": 1,
        "key": "shared_key",
        "data": {"side": "built-in"},
    }
    save = pb.StoreSave(key="shared_key")
    save.data = encode_json(wrapped)
    try:
        await sandbox_a.call("sandbox/store_save", save)
        # The custom-group bridge cannot see built-in's data.
        loaded_custom = await sandbox_b.call(
            "sandbox/store_load", pb.StoreLoad(key="shared_key")
        )
    finally:
        await main_a.close()
        await sandbox_a.close()
        await main_b.close()
        await sandbox_b.close()

    # proto: the custom group has no entry, so `data` is unset.
    assert not loaded_custom.HasField("data")
    assert _store_path(hass, "built-in", "shared_key").is_file()
    assert not _store_path(hass, "custom", "shared_key").exists()


async def test_store_survives_bridge_restart(hass: HomeAssistant) -> None:
    """A fresh bridge (sim sandbox restart) reads previously-saved data."""
    _bridge1, main_a, sandbox_a = await _wire(hass, group="built-in")
    wrapped: dict[str, Any] = {
        "version": 4,
        "minor_version": 0,
        "key": "persistent",
        "data": {"survives": True},
    }
    save = pb.StoreSave(key="persistent")
    save.data = encode_json(wrapped)
    try:
        await sandbox_a.call("sandbox/store_save", save)
    finally:
        await main_a.close()
        await sandbox_a.close()

    # Bring up a fresh bridge for the same group on a new channel pair.
    _bridge2, main_b, sandbox_b = await _wire(hass, group="built-in")
    try:
        loaded = await sandbox_b.call(
            "sandbox/store_load", pb.StoreLoad(key="persistent")
        )
    finally:
        await main_b.close()
        await sandbox_b.close()

    assert decode_json_dict(loaded.data) == wrapped

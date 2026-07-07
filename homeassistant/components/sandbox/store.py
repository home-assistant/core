"""Main-side store backend for the ``sandbox/store_*`` routing handlers.

Each :class:`~.bridge.SandboxBridge` owns one :class:`SandboxStoreServer`,
writing each key to ``<config>/.storage/sandbox/<group>/<key>``. Scope
isolation is by construction — each bridge owns one channel for one group,
so a sandbox can't reach another sandbox's files. :func:`validate_key`
defends the host filesystem from a hostile wire key.
"""

import logging
import os
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import json as json_helper
from homeassistant.helpers.storage import STORAGE_DIR
from homeassistant.util import json as json_util
from homeassistant.util.file import write_utf8_file_atomic

_LOGGER = logging.getLogger(__name__)

_STORE_KEY_FORBIDDEN = ("/", "\\", "\x00")

# Store quota constants. A real integration's ``.storage`` payload is KBs to a
# low-MB; these are generous-but-finite so a compromised sandbox cannot exhaust
# the host disk through the store-routing channel (the only other bound is the
# 16 MB per-frame cap). Overridable here if a legitimate integration needs more.
#
# * key length: well under ``NAME_MAX`` (255) so the on-disk filename is always
#   valid even after any future suffixing.
# * per-key value: one ``Store`` payload; 4 MB covers large registries.
# * per-group total + key count: bound the whole ``sandbox/<group>/`` dir.
STORE_MAX_KEY_LENGTH = 128
STORE_MAX_VALUE_BYTES = 4 * 1024 * 1024
STORE_MAX_TOTAL_BYTES = 32 * 1024 * 1024
STORE_MAX_KEYS = 256


def validate_key(key: str) -> str:
    """Validate a store ``key`` from the wire.

    Defends the host filesystem from a compromised sandbox: a key must
    be a non-empty string within the length cap, with no path separators,
    no null bytes, and no parent-directory hop. Anything else trips a
    :class:`HomeAssistantError`, which the channel framework turns into
    a remote-error frame for the sandbox.
    """
    if not key:
        raise HomeAssistantError("store request: missing 'key'")
    if len(key) > STORE_MAX_KEY_LENGTH:
        raise HomeAssistantError(
            f"store request: key too long ({len(key)} > {STORE_MAX_KEY_LENGTH})"
        )
    if any(ch in key for ch in _STORE_KEY_FORBIDDEN):
        raise HomeAssistantError(f"store request: invalid key {key!r}")
    if key in {".", ".."} or key.startswith(".."):
        raise HomeAssistantError(f"store request: invalid key {key!r}")
    return key


class SandboxStoreServer:
    """Per-group store backend on main.

    Each :class:`~.bridge.SandboxBridge` owns one of these. The bridge's
    channel is dedicated to one sandbox group, so scope isolation is enforced
    by construction: sandbox "built-in" only ever talks to its own bridge,
    which only ever reads/writes ``<config>/.storage/sandbox/built-in/``.
    Cross-group access requires forging a channel, which the sandbox
    cannot do.
    """

    def __init__(self, hass: HomeAssistant, group: str) -> None:
        """Pin the storage directory to ``<config>/.storage/sandbox/<group>``."""
        self.hass = hass
        self.group = group
        self._dir = Path(hass.config.path(STORAGE_DIR, "sandbox", group))

    def _path_for(self, key: str) -> Path:
        # ``validate_key`` has already rejected slashes / ``..`` / NUL.
        return self._dir / key

    async def async_load(self, key: str) -> dict[str, Any] | None:
        """Return the wrapped Store payload or ``None`` if missing."""
        path = self._path_for(key)
        try:
            data = await self.hass.async_add_executor_job(
                json_util.load_json, str(path), None
            )
        except HomeAssistantError as err:
            _LOGGER.warning(
                "Sandbox %s store_load(%s) failed: %s", self.group, key, err
            )
            return None
        if data is None or data == {}:
            return None
        if not isinstance(data, dict):
            _LOGGER.warning(
                "Sandbox %s store_load(%s): non-dict on disk (%s)",
                self.group,
                key,
                type(data).__name__,
            )
            return None
        return data

    async def async_save(self, key: str, data: dict[str, Any]) -> None:
        """Write the wrapped Store payload atomically, within quota.

        Rejects (with a :class:`HomeAssistantError` → remote-error frame) a
        value over the per-key cap or a write that would push the group's
        ``.storage/sandbox/<group>/`` dir past its byte / key-count quota, so a
        compromised sandbox cannot exhaust the host disk. The sandbox-side
        ``Store.async_save`` tolerates a failed write (it logs and keeps the
        in-memory data), so a rejected flush degrades rather than crashing.
        """
        path = self._path_for(key)
        await self.hass.async_add_executor_job(self._write_sync, path, data)

    def _write_sync(self, path: Path, data: dict[str, Any]) -> None:
        mode, json_data = json_helper.prepare_save_json(data, encoder=None)
        value_bytes = len(
            json_data if isinstance(json_data, bytes) else json_data.encode("utf-8")
        )
        if value_bytes > STORE_MAX_VALUE_BYTES:
            raise HomeAssistantError(
                f"store_save: value too large ({value_bytes} > "
                f"{STORE_MAX_VALUE_BYTES} bytes) for group {self.group!r}"
            )
        os.makedirs(path.parent, exist_ok=True)
        self._enforce_group_quota(path, value_bytes)
        write_utf8_file_atomic(str(path), json_data, False, mode=mode)

    def _enforce_group_quota(self, path: Path, value_bytes: int) -> None:
        """Reject a write that would exceed the per-group disk quota.

        Sums the existing files in the group dir (the one being overwritten
        counts as its new size, not its old), so a steady rewrite of the same
        key never trips the cap while unbounded *growth* — new keys or ballooning
        values — is bounded.
        """
        total = value_bytes
        keys = 1
        with os.scandir(path.parent) as entries:
            for entry in entries:
                if not entry.is_file() or entry.name == path.name:
                    continue
                keys += 1
                total += entry.stat().st_size
        if keys > STORE_MAX_KEYS:
            raise HomeAssistantError(
                f"store_save: too many keys ({keys} > {STORE_MAX_KEYS}) for "
                f"group {self.group!r}"
            )
        if total > STORE_MAX_TOTAL_BYTES:
            raise HomeAssistantError(
                f"store_save: group {self.group!r} over quota ({total} > "
                f"{STORE_MAX_TOTAL_BYTES} bytes)"
            )

    async def async_remove(self, key: str) -> None:
        """Unlink the file backing ``key`` if it exists."""
        path = self._path_for(key)
        await self.hass.async_add_executor_job(self._remove_sync, path)

    def _remove_sync(self, path: Path) -> None:
        try:
            os.unlink(path)
        except FileNotFoundError:
            return


__all__ = [
    "STORE_MAX_KEYS",
    "STORE_MAX_KEY_LENGTH",
    "STORE_MAX_TOTAL_BYTES",
    "STORE_MAX_VALUE_BYTES",
    "SandboxStoreServer",
    "validate_key",
]

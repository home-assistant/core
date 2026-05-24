"""Sandbox-side :class:`RemoteStore` — routes ``Store`` IO to main.

Phase 8: the sandbox runtime swaps ``homeassistant.helpers.storage.Store``
with :class:`RemoteStore` once the control channel is ready, so every
``Store(hass, version, key, …)`` call from an integration returns a
RemoteStore that proxies ``async_load`` / ``async_save`` / ``async_remove``
to main. Main namespaces every key as
``<config>/.storage/sandbox_v2/<group>/<key>`` so two sandbox processes —
or main itself — can't read each other's data.

The patch installs lazily: registries that already loaded against the
sandbox-private tempdir (``core.device_registry`` and friends) keep
their local file backing. Integrations that instantiate ``Store`` after
the install — i.e. during ``async_setup_entry`` — get a RemoteStore.

``delay_save`` semantics are unchanged: :class:`RemoteStore` overrides
only the disk-IO primitives (:meth:`_async_load_data`,
:meth:`_async_write_data`, :meth:`async_remove`); batching, the final-
write hook, and the migration loop run unchanged from
:class:`Store`.
"""

from collections.abc import Callable
from copy import deepcopy
import inspect
import json
import logging
from typing import Any, ClassVar

from homeassistant.exceptions import UnsupportedStorageVersionError
from homeassistant.helpers import json as json_helper, storage as _storage
from homeassistant.util.json import SerializationError

from .channel import Channel, ChannelClosedError, ChannelRemoteError
from .protocol import MSG_STORE_LOAD, MSG_STORE_REMOVE, MSG_STORE_SAVE

_LOGGER = logging.getLogger(__name__)

_BaseStore = _storage.Store


class RemoteStore(_BaseStore):
    """``Store`` subclass that persists via :class:`Channel` to main.

    Class-level :attr:`_channel` is set by :func:`install_remote_store`
    and cleared by the uninstall callable it returns. There is exactly
    one channel per sandbox runtime, so a class attribute is enough —
    every ``Store`` instance the sandbox builds shares it.
    """

    _channel: ClassVar[Channel | None] = None

    @classmethod
    def _remote_channel(cls) -> Channel | None:
        return cls._channel

    async def _async_load_data(self) -> Any:
        """Load the wrapped payload from main, then run any migration.

        Mirrors :meth:`Store._async_load_data` but bypasses the on-disk
        path and the file-cache manager — main is the source of truth.
        The migration block matches ``Store`` line-for-line so an
        integration that ships a ``_async_migrate_func`` keeps working.
        """
        if self._load_empty:
            self.make_read_only()
            return None

        if self._data is not None:
            data = self._data
            if "data_func" in data:
                data["data"] = data.pop("data_func")()
            data = deepcopy(data)
        else:
            wrapped = await self._remote_load()
            if wrapped is None:
                return None
            data = wrapped

        if "minor_version" not in data:
            data["minor_version"] = 1

        if (
            data["version"] == self.version
            and data["minor_version"] == self.minor_version
        ):
            return data["data"]

        if data["version"] > self._max_readable_version:
            raise UnsupportedStorageVersionError(
                self.key, data["version"], self._max_readable_version
            )
        _LOGGER.info(
            "Migrating %s storage from %s.%s to %s.%s",
            self.key,
            data["version"],
            data["minor_version"],
            self.version,
            self.minor_version,
        )
        if len(inspect.signature(self._async_migrate_func).parameters) == 2:
            stored = await self._async_migrate_func(data["version"], data["data"])
        else:
            try:
                stored = await self._async_migrate_func(
                    data["version"], data["minor_version"], data["data"]
                )
            except NotImplementedError:
                if data["version"] != self.version:
                    raise
                stored = data["data"]
        await self.async_save(stored)
        return stored

    async def _remote_load(self) -> dict[str, Any] | None:
        """Fetch the wrapped dict for ``self.key`` from main."""
        channel = self._remote_channel()
        if channel is None:
            _LOGGER.error("RemoteStore[%s]: load before install", self.key)
            return None
        try:
            wrapped = await channel.call(MSG_STORE_LOAD, {"key": self.key})
        except ChannelClosedError:
            _LOGGER.warning("RemoteStore[%s]: channel closed mid-load", self.key)
            return None
        except ChannelRemoteError as err:
            _LOGGER.warning("RemoteStore[%s] load failed: %s", self.key, err)
            return None
        if wrapped is None:
            return None
        if not isinstance(wrapped, dict):
            _LOGGER.error(
                "RemoteStore[%s]: main returned non-dict (%s)",
                self.key,
                type(wrapped).__name__,
            )
            return None
        return wrapped

    async def _async_write_data(self, data: dict) -> None:
        """Push the wrapped payload to main instead of writing to disk.

        ``Store`` callers may hand us HA-specific types (``Fragment`` from
        ``State.json_fragment``, ``set``/``tuple``, ``datetime``, ``Path``,
        ``as_dict``-shaped objects). The channel transports plain JSON, so
        we run the payload through orjson's HA-aware encoder first and
        parse the resulting bytes back to primitives before handing it
        off. Same trip ``Store.async_save`` would take on its way to disk
        — we just intercept before the bytes hit a file.
        """
        channel = self._remote_channel()
        if channel is None:
            _LOGGER.error("RemoteStore[%s]: save before install", self.key)
            return
        if "data_func" in data:
            data["data"] = data.pop("data_func")()
        try:
            _mode, json_bytes = json_helper.prepare_save_json(data, encoder=None)
            payload = json.loads(json_bytes)
        except SerializationError:
            _LOGGER.exception("RemoteStore[%s]: payload not serialisable", self.key)
            return
        try:
            await channel.call(MSG_STORE_SAVE, {"key": self.key, "data": payload})
        except ChannelClosedError:
            _LOGGER.warning("RemoteStore[%s]: channel closed mid-save", self.key)
        except ChannelRemoteError as err:
            _LOGGER.error("RemoteStore[%s] save failed: %s", self.key, err)

    async def async_remove(self) -> None:
        """Mirror :meth:`Store.async_remove` but unlink on main, not locally."""
        self._manager.async_invalidate(self.key)
        self._async_cleanup_delay_listener()
        self._async_cleanup_final_write_listener()
        channel = self._remote_channel()
        if channel is None:
            return
        try:
            await channel.call(MSG_STORE_REMOVE, {"key": self.key})
        except ChannelClosedError:
            _LOGGER.warning("RemoteStore[%s]: channel closed mid-remove", self.key)
        except ChannelRemoteError as err:
            _LOGGER.warning("RemoteStore[%s] remove failed: %s", self.key, err)


def install_remote_store(channel: Channel) -> Callable[[], None]:
    """Patch ``homeassistant.helpers.storage.Store`` with :class:`RemoteStore`.

    Returns an idempotent uninstall callable that restores the original
    ``Store`` class. Tests that don't tear the patch down at fixture
    teardown will leak the patch into the next test, so always call the
    returned uninstaller.

    The patch is process-wide on purpose — every ``Store(...)`` call
    inside the sandbox routes through ``RemoteStore``. The sandbox
    process hosts one sandbox group, so a single class-level
    :attr:`RemoteStore._channel` is correct.
    """
    RemoteStore._channel = channel  # noqa: SLF001 — own class attr
    _storage.Store = RemoteStore  # type: ignore[misc]

    def _uninstall() -> None:
        if _storage.Store is RemoteStore:
            _storage.Store = _BaseStore  # type: ignore[misc]
        RemoteStore._channel = None  # noqa: SLF001

    return _uninstall


__all__ = ["RemoteStore", "install_remote_store"]

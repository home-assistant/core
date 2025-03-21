"""Helper to help store data."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import suppress
from copy import deepcopy
import inspect
from json import JSONDecodeError, JSONEncoder
import logging
import os
from pathlib import Path
from typing import Any

from propcache.api import cached_property

from homeassistant.const import (
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.core import (
    CALLBACK_TYPE,
    DOMAIN as HOMEASSISTANT_DOMAIN,
    CoreState,
    Event,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import bind_hass
from homeassistant.util import dt as dt_util, json as json_util
from homeassistant.util.file import WriteError
from homeassistant.util.hass_dict import HassKey

from . import json as json_helper

# mypy: allow-untyped-calls, allow-untyped-defs, no-warn-return-any
# mypy: no-check-untyped-defs
MAX_LOAD_CONCURRENTLY = 6

STORAGE_DIR = ".storage"
_LOGGER = logging.getLogger(__name__)

STORAGE_SEMAPHORE: HassKey[asyncio.Semaphore] = HassKey("storage_semaphore")
STORAGE_MANAGER: HassKey[_StoreManager] = HassKey("storage_manager")

MANAGER_CLEANUP_DELAY = 60


@bind_hass
async def async_migrator[_T: Mapping[str, Any] | Sequence[Any]](
    hass: HomeAssistant,
    old_path: str,
    store: Store[_T],
    *,
    old_conf_load_func: Callable | None = None,
    old_conf_migrate_func: Callable | None = None,
) -> _T | None:
    """Migrate old data to a store and then load data.

    async def old_conf_migrate_func(old_data)
    """
    # If we already have store data we have already migrated in the past.
    if (store_data := await store.async_load()) is not None:
        return store_data

    def load_old_config():
        """Load old config."""
        if not os.path.isfile(old_path):
            return None

        if old_conf_load_func is not None:
            return old_conf_load_func(old_path)

        return json_util.load_json(old_path)

    config = await hass.async_add_executor_job(load_old_config)

    if config is None:
        return None

    if old_conf_migrate_func is not None:
        config = await old_conf_migrate_func(config)

    await store.async_save(config)
    await hass.async_add_executor_job(os.remove, old_path)
    return config


def get_internal_store_manager(hass: HomeAssistant) -> _StoreManager:
    """Get the store manager.

    This function is not part of the API and should only be
    used in the Home Assistant core internals. It is not
    guaranteed to be stable.
    """
    if STORAGE_MANAGER not in hass.data:
        manager = _StoreManager(hass)
        hass.data[STORAGE_MANAGER] = manager
    return hass.data[STORAGE_MANAGER]


class _StoreManager:
    """Class to help storing data.

    The store manager is used to cache and manage storage files.
    """

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize storage manager class."""
        self._hass = hass
        self._invalidated: set[str] = set()
        self._files: set[str] | None = None
        self._data_preload: dict[str, json_util.JsonValueType] = {}
        self._storage_path: Path = Path(hass.config.config_dir).joinpath(STORAGE_DIR)
        self._cancel_cleanup: asyncio.TimerHandle | None = None

    async def async_initialize(self) -> None:
        """Initialize the storage manager."""
        hass = self._hass
        await hass.async_add_executor_job(self._initialize_files)
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED,
            self._async_schedule_cleanup,
        )

    @callback
    def async_invalidate(self, key: str) -> None:
        """Invalidate cache.

        Store calls this when its going to save data
        to ensure that the cache is not used after that.
        """
        if "/" not in key:
            self._invalidated.add(key)
            self._data_preload.pop(key, None)

    @callback
    def async_fetch(
        self, key: str
    ) -> tuple[bool, json_util.JsonValueType | None] | None:
        """Fetch data from cache."""
        #
        # If the key is invalidated, we don't need to check the cache
        # If async_initialize has not been called yet, we don't know
        # if the file exists or not so its a cache miss
        #
        # It is very important that we check if self._files is None
        # because we do not want to incorrectly return a cache miss
        # because async_initialize has not been called yet as it would
        # cause the Store to return None when it should not.
        #
        # The "/" in key check is to prevent the cache from being used
        # for subdirs in case we have a key like "hacs/XXX"
        #
        if "/" in key or key in self._invalidated or self._files is None:
            _LOGGER.debug("%s: Cache miss", key)
            return None

        # If async_initialize has been called and the key is not in self._files
        # then the file does not exist
        if key not in self._files:
            _LOGGER.debug("%s: Cache hit, does not exist", key)
            return (False, None)

        # If the key is in the preload cache, return it
        if data := self._data_preload.pop(key, None):
            _LOGGER.debug("%s: Cache hit data", key)
            return (True, data)

        _LOGGER.debug("%s: Cache miss, not preloaded", key)
        return None

    @callback
    def _async_schedule_cleanup(self, _event: Event) -> None:
        """Schedule the cleanup of old files."""
        self._cancel_cleanup = self._hass.loop.call_later(
            MANAGER_CLEANUP_DELAY, self._async_cleanup
        )
        # Handle the case where we stop in the first 60s
        self._hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP,
            self._async_cancel_and_cleanup,
        )

    @callback
    def _async_cancel_and_cleanup(self, _event: Event) -> None:
        """Cancel the cleanup of old files."""
        self._async_cleanup()
        if self._cancel_cleanup:
            self._cancel_cleanup.cancel()
            self._cancel_cleanup = None

    @callback
    def _async_cleanup(self) -> None:
        """Cleanup unused cache.

        If nothing consumes the cache 60s after startup or when we
        stop Home Assistant, we'll clear the cache.
        """
        self._data_preload.clear()

    async def async_preload(self, keys: Iterable[str]) -> None:
        """Cache the keys."""
        # If async_initialize has not been called yet, we can't preload
        if self._files is not None and (existing := self._files.intersection(keys)):
            await self._hass.async_add_executor_job(self._preload, existing)

    def _preload(self, keys: Iterable[str]) -> None:
        """Cache the keys."""
        storage_path = self._storage_path
        data_preload = self._data_preload
        for key in keys:
            storage_file: Path = storage_path.joinpath(key)
            try:
                if storage_file.is_file():
                    data_preload[key] = json_util.load_json(storage_file)
            except Exception as ex:  # noqa: BLE001
                _LOGGER.debug("Error loading %s: %s", key, ex)

    def _initialize_files(self) -> None:
        """Initialize the cache."""
        if self._storage_path.exists():
            self._files = set(os.listdir(self._storage_path))


@bind_hass
class Store[_T: Mapping[str, Any] | Sequence[Any]]:
    """Class to help storing data."""

    def __init__(
        self,
        hass: HomeAssistant,
        version: int,
        key: str,
        private: bool = False,
        *,
        atomic_writes: bool = False,
        encoder: type[JSONEncoder] | None = None,
        minor_version: int = 1,
        read_only: bool = False,
    ) -> None:
        """Initialize storage class."""
        self.version = version
        self.minor_version = minor_version
        self.key = key
        self.hass = hass
        self._private = private
        self._data: dict[str, Any] | None = None
        self._delay_handle: asyncio.TimerHandle | None = None
        self._unsub_final_write_listener: CALLBACK_TYPE | None = None
        self._write_lock = asyncio.Lock()
        self._load_future: asyncio.Future[_T | None] | None = None
        self._encoder = encoder
        self._atomic_writes = atomic_writes
        self._read_only = read_only
        self._next_write_time = 0.0
        self._manager = get_internal_store_manager(hass)

    @cached_property
    def path(self):
        """Return the config path."""
        return self.hass.config.path(STORAGE_DIR, self.key)

    def make_read_only(self) -> None:
        """Make the store read-only.

        This method is irreversible.
        """
        self._read_only = True

    async def async_load(self) -> _T | None:
        """Load data.

        If the expected version and minor version do not match the given
        versions, the migrate function will be invoked with
        migrate_func(version, minor_version, config).

        Will ensure that when a call comes in while another one is in progress,
        the second call will wait and return the result of the first call.
        """
        if self._load_future:
            return await self._load_future

        self._load_future = self.hass.loop.create_future()
        try:
            result = await self._async_load()
        except BaseException as ex:
            self._load_future.set_exception(ex)
            # Ensure the future is marked as retrieved
            # since if there is no concurrent call it
            # will otherwise never be retrieved.
            self._load_future.exception()
            raise
        else:
            self._load_future.set_result(result)
        finally:
            self._load_future = None

        return result

    async def _async_load(self) -> _T | None:
        """Load the data and ensure the task is removed."""
        if STORAGE_SEMAPHORE not in self.hass.data:
            self.hass.data[STORAGE_SEMAPHORE] = asyncio.Semaphore(MAX_LOAD_CONCURRENTLY)
        async with self.hass.data[STORAGE_SEMAPHORE]:
            return await self._async_load_data()

    async def _async_load_data(self):
        """Load the data."""
        # Check if we have a pending write
        if self._data is not None:
            data = self._data

            # If we didn't generate data yet, do it now.
            if "data_func" in data:
                data["data"] = data.pop("data_func")()

            # We make a copy because code might assume it's safe to mutate loaded data
            # and we don't want that to mess with what we're trying to store.
            data = deepcopy(data)
        elif cache := self._manager.async_fetch(self.key):
            exists, data = cache
            if not exists:
                return None
        else:
            try:
                data = await self.hass.async_add_executor_job(
                    json_util.load_json, self.path
                )
            except HomeAssistantError as err:
                if isinstance(err.__cause__, JSONDecodeError):
                    # If we have a JSONDecodeError, it means the file is corrupt.
                    # We can't recover from this, so we'll log an error, rename the file and
                    # return None so that we can start with a clean slate which will
                    # allow startup to continue so they can restore from a backup.
                    isotime = dt_util.utcnow().isoformat()
                    corrupt_postfix = f".corrupt.{isotime}"
                    corrupt_path = f"{self.path}{corrupt_postfix}"
                    await self.hass.async_add_executor_job(
                        os.rename, self.path, corrupt_path
                    )
                    storage_key = self.key
                    _LOGGER.error(
                        "Unrecoverable error decoding storage %s at %s; "
                        "This may indicate an unclean shutdown, invalid syntax "
                        "from manual edits, or disk corruption; "
                        "The corrupt file has been saved as %s; "
                        "It is recommended to restore from backup: %s",
                        storage_key,
                        self.path,
                        corrupt_path,
                        err,
                    )
                    from .issue_registry import (  # pylint: disable=import-outside-toplevel
                        IssueSeverity,
                        async_create_issue,
                    )

                    issue_domain = HOMEASSISTANT_DOMAIN
                    if (
                        domain := (storage_key.partition(".")[0])
                    ) and domain in self.hass.config.components:
                        issue_domain = domain

                    async_create_issue(
                        self.hass,
                        HOMEASSISTANT_DOMAIN,
                        f"storage_corruption_{storage_key}_{isotime}",
                        is_fixable=True,
                        issue_domain=issue_domain,
                        translation_key="storage_corruption",
                        is_persistent=True,
                        severity=IssueSeverity.CRITICAL,
                        translation_placeholders={
                            "storage_key": storage_key,
                            "original_path": self.path,
                            "corrupt_path": corrupt_path,
                            "error": str(err),
                        },
                    )
                    return None
                raise

            if data == {}:
                return None

        # Add minor_version if not set
        if "minor_version" not in data:
            data["minor_version"] = 1

        if (
            data["version"] == self.version
            and data["minor_version"] == self.minor_version
        ):
            stored = data["data"]
        else:
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

    async def async_save(self, data: _T) -> None:
        """Save data."""
        self._data = {
            "version": self.version,
            "minor_version": self.minor_version,
            "key": self.key,
            "data": data,
        }

        if self.hass.state is CoreState.stopping:
            self._async_ensure_final_write_listener()
            return

        await self._async_handle_write_data()

    @callback
    def async_delay_save(
        self,
        data_func: Callable[[], _T],
        delay: float = 0,
    ) -> None:
        """Save data with an optional delay."""
        self._data = {
            "version": self.version,
            "minor_version": self.minor_version,
            "key": self.key,
            "data_func": data_func,
        }

        next_when = self.hass.loop.time() + delay
        if self._delay_handle and self._delay_handle.when() < next_when:
            self._next_write_time = next_when
            return

        self._async_cleanup_delay_listener()
        self._async_ensure_final_write_listener()

        if self.hass.state is CoreState.stopping:
            return

        # We use call_later directly here to avoid a circular import
        self._async_reschedule_delayed_write(next_when)

    @callback
    def _async_reschedule_delayed_write(self, when: float) -> None:
        """Reschedule a delayed write."""
        self._delay_handle = self.hass.loop.call_at(
            when, self._async_schedule_callback_delayed_write
        )

    @callback
    def _async_schedule_callback_delayed_write(self) -> None:
        """Schedule the delayed write in a task."""
        if self.hass.loop.time() < self._next_write_time:
            # Timer fired too early because there were multiple
            # calls to async_delay_save before the first one
            # wrote. Reschedule the timer to the next write time.
            self._async_reschedule_delayed_write(self._next_write_time)
            return
        self.hass.async_create_task_internal(
            self._async_callback_delayed_write(), eager_start=True
        )

    @callback
    def _async_ensure_final_write_listener(self) -> None:
        """Ensure that we write if we quit before delay has passed."""
        if self._unsub_final_write_listener is None:
            self._unsub_final_write_listener = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_FINAL_WRITE,
                self._async_callback_final_write,
            )

    @callback
    def _async_cleanup_final_write_listener(self) -> None:
        """Clean up a stop listener."""
        if self._unsub_final_write_listener is not None:
            self._unsub_final_write_listener()
            self._unsub_final_write_listener = None

    @callback
    def _async_cleanup_delay_listener(self) -> None:
        """Clean up a delay listener."""
        if self._delay_handle is not None:
            self._delay_handle.cancel()
            self._delay_handle = None

    async def _async_callback_delayed_write(self) -> None:
        """Handle a delayed write callback."""
        # catch the case where a call is scheduled and then we stop Home Assistant
        if self.hass.state is CoreState.stopping:
            self._async_ensure_final_write_listener()
            return
        await self._async_handle_write_data()

    async def _async_callback_final_write(self, _event: Event) -> None:
        """Handle a write because Home Assistant is in final write state."""
        self._unsub_final_write_listener = None
        await self._async_handle_write_data()

    async def _async_handle_write_data(self, *_args):
        """Handle writing the config."""
        async with self._write_lock:
            self._manager.async_invalidate(self.key)
            self._async_cleanup_delay_listener()
            self._async_cleanup_final_write_listener()

            if self._data is None:
                # Another write already consumed the data
                return

            data = self._data
            self._data = None

            if self._read_only:
                return

            try:
                await self._async_write_data(self.path, data)
            except (json_util.SerializationError, WriteError) as err:
                _LOGGER.error("Error writing config for %s: %s", self.key, err)

    async def _async_write_data(self, path: str, data: dict) -> None:
        await self.hass.async_add_executor_job(self._write_data, self.path, data)

    def _write_data(self, path: str, data: dict) -> None:
        """Write the data."""
        os.makedirs(os.path.dirname(path), exist_ok=True)

        if "data_func" in data:
            data["data"] = data.pop("data_func")()

        _LOGGER.debug("Writing data for %s to %s", self.key, path)
        json_helper.save_json(
            path,
            data,
            self._private,
            encoder=self._encoder,
            atomic_writes=self._atomic_writes,
        )

    async def _async_migrate_func(self, old_major_version, old_minor_version, old_data):
        """Migrate to the new version."""
        raise NotImplementedError

    async def async_remove(self) -> None:
        """Remove all data."""
        self._manager.async_invalidate(self.key)
        self._async_cleanup_delay_listener()
        self._async_cleanup_final_write_listener()

        with suppress(FileNotFoundError):
            await self.hass.async_add_executor_job(os.unlink, self.path)

"""Helper to help store data."""
from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping, Sequence
from contextlib import suppress
from copy import deepcopy
import inspect
from json import JSONDecodeError, JSONEncoder
import logging
import os
from typing import Any, Generic, TypeVar

from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.core import (
    CALLBACK_TYPE,
    DOMAIN as HOMEASSISTANT_DOMAIN,
    CoreState,
    Event,
    HomeAssistant,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.loader import MAX_LOAD_CONCURRENTLY, bind_hass
from homeassistant.util import json as json_util
import homeassistant.util.dt as dt_util
from homeassistant.util.file import WriteError

from . import json as json_helper

# mypy: allow-untyped-calls, allow-untyped-defs, no-warn-return-any
# mypy: no-check-untyped-defs

STORAGE_DIR = ".storage"
_LOGGER = logging.getLogger(__name__)

STORAGE_SEMAPHORE = "storage_semaphore"

_T = TypeVar("_T", bound=Mapping[str, Any] | Sequence[Any])


@bind_hass
async def async_migrator(
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


@bind_hass
class Store(Generic[_T]):
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
    ) -> None:
        """Initialize storage class."""
        self.version = version
        self.minor_version = minor_version
        self.key = key
        self.hass = hass
        self._private = private
        self._data: dict[str, Any] | None = None
        self._unsub_delay_listener: CALLBACK_TYPE | None = None
        self._unsub_final_write_listener: CALLBACK_TYPE | None = None
        self._write_lock = asyncio.Lock()
        self._load_task: asyncio.Future[_T | None] | None = None
        self._encoder = encoder
        self._atomic_writes = atomic_writes

    @property
    def path(self):
        """Return the config path."""
        return self.hass.config.path(STORAGE_DIR, self.key)

    async def async_load(self) -> _T | None:
        """Load data.

        If the expected version and minor version do not match the given
        versions, the migrate function will be invoked with
        migrate_func(version, minor_version, config).

        Will ensure that when a call comes in while another one is in progress,
        the second call will wait and return the result of the first call.
        """
        if self._load_task is None:
            self._load_task = self.hass.async_create_task(
                self._async_load(), f"Storage load {self.key}"
            )

        return await self._load_task

    async def _async_load(self) -> _T | None:
        """Load the data and ensure the task is removed."""
        if STORAGE_SEMAPHORE not in self.hass.data:
            self.hass.data[STORAGE_SEMAPHORE] = asyncio.Semaphore(MAX_LOAD_CONCURRENTLY)

        try:
            async with self.hass.data[STORAGE_SEMAPHORE]:
                return await self._async_load_data()
        finally:
            self._load_task = None

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
                # pylint: disable-next=no-value-for-parameter
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

        if self.hass.state == CoreState.stopping:
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
        # pylint: disable-next=import-outside-toplevel
        from .event import async_call_later

        self._data = {
            "version": self.version,
            "minor_version": self.minor_version,
            "key": self.key,
            "data_func": data_func,
        }

        self._async_cleanup_delay_listener()
        self._async_ensure_final_write_listener()

        if self.hass.state == CoreState.stopping:
            return

        self._unsub_delay_listener = async_call_later(
            self.hass, delay, self._async_callback_delayed_write
        )

    @callback
    def _async_ensure_final_write_listener(self) -> None:
        """Ensure that we write if we quit before delay has passed."""
        if self._unsub_final_write_listener is None:
            self._unsub_final_write_listener = self.hass.bus.async_listen_once(
                EVENT_HOMEASSISTANT_FINAL_WRITE, self._async_callback_final_write
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
        if self._unsub_delay_listener is not None:
            self._unsub_delay_listener()
            self._unsub_delay_listener = None

    async def _async_callback_delayed_write(self, _now):
        """Handle a delayed write callback."""
        # catch the case where a call is scheduled and then we stop Home Assistant
        if self.hass.state == CoreState.stopping:
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
            self._async_cleanup_delay_listener()
            self._async_cleanup_final_write_listener()

            if self._data is None:
                # Another write already consumed the data
                return

            data = self._data

            if "data_func" in data:
                data["data"] = data.pop("data_func")()

            self._data = None

            try:
                await self._async_write_data(self.path, data)
            except (json_util.SerializationError, WriteError) as err:
                _LOGGER.error("Error writing config for %s: %s", self.key, err)

    async def _async_write_data(self, path: str, data: dict) -> None:
        await self.hass.async_add_executor_job(self._write_data, self.path, data)

    def _write_data(self, path: str, data: dict) -> None:
        """Write the data."""
        os.makedirs(os.path.dirname(path), exist_ok=True)

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
        self._async_cleanup_delay_listener()
        self._async_cleanup_final_write_listener()

        with suppress(FileNotFoundError):
            await self.hass.async_add_executor_job(os.unlink, self.path)

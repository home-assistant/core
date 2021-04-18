"""Helper to help store data."""
from __future__ import annotations

import asyncio
from contextlib import suppress
from json import JSONEncoder
import logging
import os
from typing import Any, Callable

from homeassistant.const import EVENT_HOMEASSISTANT_FINAL_WRITE
from homeassistant.core import CALLBACK_TYPE, CoreState, Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.loader import bind_hass
from homeassistant.util import json as json_util

# mypy: allow-untyped-calls, allow-untyped-defs, no-warn-return-any
# mypy: no-check-untyped-defs

STORAGE_DIR = ".storage"
_LOGGER = logging.getLogger(__name__)


@bind_hass
async def async_migrator(
    hass,
    old_path,
    store,
    *,
    old_conf_load_func=None,
    old_conf_migrate_func=None,
):
    """Migrate old data to a store and then load data.

    async def old_conf_migrate_func(old_data)
    """
    store_data = await store.async_load()

    # If we already have store data we have already migrated in the past.
    if store_data is not None:
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
class Store:
    """Class to help storing data."""

    def __init__(
        self,
        hass: HomeAssistant,
        version: int,
        key: str,
        private: bool = False,
        *,
        encoder: type[JSONEncoder] | None = None,
    ):
        """Initialize storage class."""
        self.version = version
        self.key = key
        self.hass = hass
        self._private = private
        self._data: dict[str, Any] | None = None
        self._unsub_delay_listener: CALLBACK_TYPE | None = None
        self._unsub_final_write_listener: CALLBACK_TYPE | None = None
        self._write_lock = asyncio.Lock()
        self._load_task: asyncio.Future | None = None
        self._encoder = encoder

    @property
    def path(self):
        """Return the config path."""
        return self.hass.config.path(STORAGE_DIR, self.key)

    async def async_load(self) -> dict | list | None:
        """Load data.

        If the expected version does not match the given version, the migrate
        function will be invoked with await migrate_func(version, config).

        Will ensure that when a call comes in while another one is in progress,
        the second call will wait and return the result of the first call.
        """
        if self._load_task is None:
            self._load_task = self.hass.async_create_task(self._async_load())

        return await self._load_task

    async def _async_load(self):
        """Load the data and ensure the task is removed."""
        try:
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
        else:
            data = await self.hass.async_add_executor_job(
                json_util.load_json, self.path
            )

            if data == {}:
                return None
        if data["version"] == self.version:
            stored = data["data"]
        else:
            _LOGGER.info(
                "Migrating %s storage from %s to %s",
                self.key,
                data["version"],
                self.version,
            )
            stored = await self._async_migrate_func(data["version"], data["data"])

        return stored

    async def async_save(self, data: dict | list) -> None:
        """Save data."""
        self._data = {"version": self.version, "key": self.key, "data": data}

        if self.hass.state == CoreState.stopping:
            self._async_ensure_final_write_listener()
            return

        await self._async_handle_write_data()

    @callback
    def async_delay_save(self, data_func: Callable[[], dict], delay: float = 0) -> None:
        """Save data with an optional delay."""
        self._data = {"version": self.version, "key": self.key, "data_func": data_func}

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
                await self.hass.async_add_executor_job(
                    self._write_data, self.path, data
                )
            except (json_util.SerializationError, json_util.WriteError) as err:
                _LOGGER.error("Error writing config for %s: %s", self.key, err)

    def _write_data(self, path: str, data: dict) -> None:
        """Write the data."""
        if not os.path.isdir(os.path.dirname(path)):
            os.makedirs(os.path.dirname(path))

        _LOGGER.debug("Writing data for %s to %s", self.key, path)
        json_util.save_json(path, data, self._private, encoder=self._encoder)

    async def _async_migrate_func(self, old_version, old_data):
        """Migrate to the new version."""
        raise NotImplementedError

    async def async_remove(self) -> None:
        """Remove all data."""
        self._async_cleanup_delay_listener()
        self._async_cleanup_final_write_listener()

        with suppress(FileNotFoundError):
            await self.hass.async_add_executor_job(os.unlink, self.path)

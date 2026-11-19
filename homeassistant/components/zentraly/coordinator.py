"""Coordinate reads and partial reports for one Zentraly device."""

import asyncio
from collections.abc import Awaitable, Callable
import logging
from typing import Any, override

from zentraly import ZentralyApiError

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import SCAN_INTERVAL
from .models import ZentralyConfigEntry, ZentralyDevice

_LOGGER = logging.getLogger(__name__)


class ZentralyUpdateCoordinator(DataUpdateCoordinator[dict[object, Any]]):
    """Share device state without coupling individual entity platforms."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ZentralyConfigEntry,
        device: ZentralyDevice,
        *,
        periodic_polling: bool = True,
    ) -> None:
        """Initialize a device-scoped coordinator using the existing connection."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=device.device_id,
            update_interval=SCAN_INTERVAL if periodic_polling else None,
        )
        self._entry = entry
        self.device = device
        self.data = {}
        self.readers: dict[object, Callable[[], Awaitable[Any]]] = {}
        self._versions: dict[object, int] = {}
        self._read_task: asyncio.Task[dict[object, Any]] | None = None

    @callback
    def async_update_partial[KeyT](self, updates: dict[KeyT, Any]) -> None:
        """Merge a report without postponing fallback reads of other fields."""
        for key, value in updates.items():
            self.data[key] = value
            self._versions[key] = self._versions.get(key, 0) + 1
        self.async_update_listeners()

    @override
    async def _async_update_data(self) -> dict[object, Any]:
        """Coalesce refreshes requested while a device read is in progress."""
        if not self.device.connected:
            return self.data
        if self._read_task is None:
            self._read_task = self._entry.async_create_background_task(
                self.hass,
                self._async_read(),
                f"Read Zentraly state: {self.device.device_id}",
            )
            self._read_task.add_done_callback(self._async_read_finished)
        return await asyncio.shield(self._read_task)

    @callback
    def _async_read_finished(self, task: asyncio.Task[dict[object, Any]]) -> None:
        """Release a completed read even if its refresh caller was cancelled."""
        self._read_task = None

    async def _async_read(self) -> dict[object, Any]:
        """Preserve newer reports and successful readings after a partial failure."""
        versions = self._versions.copy()
        tasks = {
            key: self.hass.async_create_task(
                self._async_read_value(reader), f"Read Zentraly {key}"
            )
            for key, reader in self.readers.items()
        }
        try:
            await asyncio.gather(*tasks.values())
        except ZentralyApiError as err:
            _LOGGER.debug("Unable to refresh %s: %s", self.device.device_id, err)
        finally:
            for task in tasks.values():
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks.values(), return_exceptions=True)
        for key, task in tasks.items():
            if (
                not task.cancelled()
                and task.exception() is None
                and self._versions.get(key, 0) == versions.get(key, 0)
            ):
                self.data[key] = task.result()
        return self.data

    async def _async_read_value(self, reader: Callable[[], Awaitable[Any]]) -> Any:
        """Adapt a library awaitable to an HA-owned coroutine task."""
        return await reader()

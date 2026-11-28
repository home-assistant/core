"""Coordinate reads and partial reports for one Zentraly device."""

import asyncio
from collections.abc import Awaitable, Callable
import logging
from typing import Any, override

from zentraly import ClimateCapability, ZentralyApiError, ZentralyClimateApi

from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SCAN_INTERVAL
from .models import ZentralyConfigEntry, ZentralyDevice

_LOGGER = logging.getLogger(__name__)
_READ_FAILED = object()
CONNECTION_TIMEOUT = 30


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
        self.climate_api = ZentralyClimateApi(device)
        self.data = {}
        self.readers: dict[object, Callable[[], Awaitable[Any]]] = {
            capability: reader
            for capability, reader in (
                (
                    ClimateCapability.LOCAL_TEMPERATURE,
                    self.climate_api.async_get_current_temperature,
                ),
                (
                    ClimateCapability.TARGET_TEMPERATURE,
                    self.climate_api.async_get_target_temperature,
                ),
                (
                    ClimateCapability.OPERATION_MODE,
                    self.climate_api.async_get_operation_mode,
                ),
                (ClimateCapability.HEAT_DEMAND, self.climate_api.async_get_heat_demand),
                (ClimateCapability.HUMIDITY, self.climate_api.async_get_humidity),
            )
            if self.climate_api.supports(capability)
        }
        self._versions: dict[object, int] = {}
        self._refresh_task: asyncio.Task[None] | None = None
        self._connected = asyncio.Event()
        self._initial_refresh_complete = False

    @override
    async def _async_setup(self) -> None:
        """Subscribe before fetching the first state from the persistent connection."""
        self._entry.async_on_unload(
            self.climate_api.add_state_listener(self.async_update_partial)
        )
        self._entry.async_on_unload(
            self.device.add_state_listener(self.async_update_listeners)
        )
        self._entry.async_on_unload(
            self.device.add_connection_state_listener(self._async_connection_changed)
        )
        if self.device.connected:
            self._connected.set()
        try:
            async with asyncio.timeout(CONNECTION_TIMEOUT):
                await self._connected.wait()
        except TimeoutError as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="setup_cannot_connect",
                translation_placeholders={"device_id": self.device.device_id},
            ) from err

    @callback
    def _async_connection_changed(self, connected: bool) -> None:
        """Publish availability and refresh state after reconnection."""
        if connected:
            self._connected.set()
            if self._initial_refresh_complete:
                self._entry.async_create_background_task(
                    self.hass,
                    self.async_refresh(),
                    f"Reconnect Zentraly state: {self.device.device_id}",
                )
        else:
            self._connected.clear()
        self.async_update_listeners()

    @callback
    def async_update_partial[KeyT](self, updates: dict[KeyT, Any]) -> None:
        """Merge a report without postponing fallback reads of other fields."""
        for key, value in updates.items():
            self.data[key] = value
            self._versions[key] = self._versions.get(key, 0) + 1
        self.last_update_success = True
        self.last_exception = None
        self.async_update_listeners()

    @override
    async def async_refresh(self) -> None:
        """Share the complete refresh before HA acquires its refresh lock."""
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = self._entry.async_create_background_task(
                self.hass,
                super().async_refresh(),
                f"Refresh Zentraly state: {self.device.device_id}",
            )
            self._refresh_task.add_done_callback(self._async_refresh_done)
        await asyncio.shield(self._refresh_task)

    @callback
    def _async_refresh_done(self, task: asyncio.Task[None]) -> None:
        """Release the refresh after HA has published its result."""
        if self._refresh_task is task:
            self._refresh_task = None

    async def async_wait_for_refresh(self) -> None:
        """Let an in-flight reconnect read finish before an entity action."""
        if self._refresh_task is not None:
            await asyncio.shield(self._refresh_task)

    @override
    async def _async_update_data(self) -> dict[object, Any]:
        """Read the state without treating a missing connection as a data loss."""
        if not self.device.connected:
            if not self._initial_refresh_complete:
                raise ConfigEntryNotReady(
                    translation_domain=DOMAIN,
                    translation_key="setup_cannot_connect",
                    translation_placeholders={"device_id": self.device.device_id},
                )
            return self.data
        data = await self._async_read()
        self._initial_refresh_complete = True
        return data

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
        finally:
            for task in tasks.values():
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks.values(), return_exceptions=True)
        for key, task in tasks.items():
            if (
                not task.cancelled()
                and task.exception() is None
                and task.result() is not _READ_FAILED
                and self._versions.get(key, 0) == versions.get(key, 0)
            ):
                self.data[key] = task.result()
        return self.data

    async def _async_read_value(self, reader: Callable[[], Awaitable[Any]]) -> Any:
        """Isolate recoverable errors in an HA-owned coroutine task."""
        try:
            return await reader()
        except ZentralyApiError as err:
            _LOGGER.debug("Unable to refresh %s: %s", self.device.device_id, err)
            return _READ_FAILED

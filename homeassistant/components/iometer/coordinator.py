"""DataUpdateCoordinator for IOmeter."""

import asyncio
from collections.abc import Callable
import contextlib
from dataclasses import dataclass
import logging
from typing import override

from iometer import (
    IOmeterConnectionError,
    IOmeterNoReadingsError,
    IOmeterNoStatusError,
    IOmeterSSEClient,
    IOmeterTimeoutError,
    Reading,
    Status,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

type IOmeterConfigEntry = ConfigEntry[IOMeterCoordinator]


@dataclass
class IOmeterData:
    """Class for data update."""

    reading: Reading
    status: Status


class IOMeterCoordinator(DataUpdateCoordinator[IOmeterData]):
    """Class to manage fetching IOmeter data."""

    config_entry: IOmeterConfigEntry
    client: IOmeterSSEClient
    current_fw_version: str = ""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: IOmeterConfigEntry,
        client: IOmeterSSEClient,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
        )
        self.client = client
        self.identifier = config_entry.entry_id
        self._reading: Reading | None = None
        self._status: Status | None = None
        self._first_data_event: asyncio.Event = asyncio.Event()
        self._cancel_readings: Callable[[], None] | None = None
        self._cancel_status: Callable[[], None] | None = None
        self._readings_task: asyncio.Task | None = None
        self._status_task: asyncio.Task | None = None

    async def async_start(self) -> None:
        """Register SSE subscriptions."""
        self._cancel_readings = self.client.subscribe_readings(
            self._on_reading,
            self._on_reading_error,
        )
        self._readings_task = getattr(self._cancel_readings, "__self__", None)
        self._cancel_status = self.client.subscribe_status(
            self._on_status,
            self._on_status_error,
        )
        self._status_task = getattr(self._cancel_status, "__self__", None)

    async def async_stop(self) -> None:
        """Cancel SSE subscriptions and await task teardown."""
        if self._cancel_readings:
            self._cancel_readings()
            self._cancel_readings = None
        if self._cancel_status:
            self._cancel_status()
            self._cancel_status = None
        for task in (self._readings_task, self._status_task):
            if task and not task.done():
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        self._readings_task = None
        self._status_task = None

    @override
    async def _async_update_data(self) -> IOmeterData:
        """Wait for first SSE data; subsequent updates arrive via async_set_updated_data."""
        try:
            async with asyncio.timeout(30):
                await self._first_data_event.wait()
        except TimeoutError as err:
            raise UpdateFailed("Timeout waiting for IOmeter data") from err
        assert self._reading is not None
        assert self._status is not None
        self._update_fw_version(self._status)
        return IOmeterData(reading=self._reading, status=self._status)

    def _on_new_data(self) -> None:
        """Called when a new reading or status arrives from SSE."""
        if self._reading is None or self._status is None:
            return
        if not self._first_data_event.is_set():
            self._first_data_event.set()
        else:
            self._update_fw_version(self._status)
            self.async_set_updated_data(
                IOmeterData(reading=self._reading, status=self._status)
            )

    def _on_reading(self, reading: Reading) -> None:
        """Handle a new reading from the SSE stream."""
        self._reading = reading
        self._on_new_data()

    def _on_status(self, status: Status) -> None:
        """Handle a new status from the SSE stream."""
        self._status = status
        self._on_new_data()

    def _on_reading_error(self, err: Exception) -> None:
        """Log reading stream errors before the library reconnects."""
        if isinstance(err, IOmeterTimeoutError):
            _LOGGER.debug("IOmeter reading stream timed out, reconnecting")
        elif isinstance(err, (IOmeterNoReadingsError, IOmeterConnectionError)):
            self._async_set_unavailable()
            _LOGGER.warning("IOmeter reading stream error: %s", err)
        else:
            self._async_set_unavailable()
            _LOGGER.exception("Unexpected error in reading stream")

    def _on_status_error(self, err: Exception) -> None:
        """Log status stream errors before the library reconnects."""
        if isinstance(err, IOmeterTimeoutError):
            _LOGGER.debug("IOmeter status stream timed out, reconnecting")
        elif isinstance(err, (IOmeterNoStatusError, IOmeterConnectionError)):
            self._async_set_unavailable()
            _LOGGER.warning("IOmeter status stream error: %s", err)
        else:
            self._async_set_unavailable()
            _LOGGER.exception("Unexpected error in status stream")

    def _async_set_unavailable(self) -> None:
        """Mark entities unavailable; skipped before first successful data."""
        if not self._first_data_event.is_set():
            return
        self.last_update_success = False
        self.async_update_listeners()

    def _update_fw_version(self, status: Status) -> None:
        """Update device registry if firmware version changed."""
        fw_version = f"{status.device.core.version}/{status.device.bridge.version}"
        if self.current_fw_version and fw_version != self.current_fw_version:
            device_registry = dr.async_get(self.hass)
            device_entry = device_registry.async_get_device(
                identifiers={(DOMAIN, status.device.id)}
            )
            if device_entry:
                device_registry.async_update_device(
                    device_entry.id,
                    sw_version=fw_version,
                )
        self.current_fw_version = fw_version

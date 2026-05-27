"""DataUpdateCoordinator for IOmeter."""

import asyncio
import contextlib
from dataclasses import dataclass
import logging

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
        self._stream_task: asyncio.Task | None = None

    async def async_start(self) -> None:
        """Start SSE listener tasks."""
        self._stream_task = self.hass.async_create_background_task(
            self._run_streams(),
            "iometer_streams",
        )

    async def async_stop(self) -> None:
        """Stop SSE listener tasks."""
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._stream_task
        self._stream_task = None

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

    async def _run_streams(self) -> None:
        """Run reading and status SSE streams concurrently."""
        async with self.client, asyncio.TaskGroup() as tg:
            tg.create_task(self._watch_readings())
            tg.create_task(self._watch_status())

    async def _watch_readings(self) -> None:
        """Consume reading SSE events, reconnecting on transient errors."""
        while True:
            try:
                async for reading in self.client.watch_readings():
                    self._reading = reading
                    self._on_new_data()
            except IOmeterTimeoutError:
                _LOGGER.debug("IOmeter reading stream timed out, reconnecting")
                await asyncio.sleep(5)
            except (IOmeterNoReadingsError, IOmeterConnectionError) as err:
                _LOGGER.warning("IOmeter reading stream error: %s", err)
                await asyncio.sleep(5)
            except Exception:
                _LOGGER.exception("Unexpected error in reading stream")
                await asyncio.sleep(5)

    async def _watch_status(self) -> None:
        """Consume status SSE events, reconnecting on transient errors."""
        while True:
            try:
                async for status in self.client.watch_status():
                    self._status = status
                    self._on_new_data()
            except IOmeterTimeoutError:
                _LOGGER.debug("IOmeter status stream timed out, reconnecting")
                await asyncio.sleep(5)
            except (IOmeterNoStatusError, IOmeterConnectionError) as err:
                _LOGGER.warning("IOmeter status stream error: %s", err)
                await asyncio.sleep(5)
            except Exception:
                _LOGGER.exception("Unexpected error in status stream")
                await asyncio.sleep(5)

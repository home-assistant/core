"""Data coordinator for Bitvis Power Hub."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime
import logging

from bitvis_protobuf import powerhub_pb2
from bitvis_protobuf.han_port_pb2 import HanPortSample
from bitvis_protobuf.powerhub_pb2 import Diagnostic
from google.protobuf.message import DecodeError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, WATCHDOG_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class BitvisData:
    """Data structure for Bitvis measurements."""

    sample: HanPortSample | None = None
    diagnostic: Diagnostic | None = None
    timestamp: datetime | None = None
    mac_address: str | None = None
    model_name: str | None = None
    sw_version: str | None = None


class BitvisUDPProtocol(asyncio.DatagramProtocol):
    """UDP protocol handler for Bitvis Power Hub."""

    def __init__(self, coordinator: BitvisDataUpdateCoordinator) -> None:
        """Initialize the protocol."""
        self.coordinator = coordinator
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        """Handle connection made."""
        assert isinstance(transport, asyncio.DatagramTransport)
        self.transport = transport
        _LOGGER.debug(
            "UDP listener started on %s", transport.get_extra_info("sockname")
        )

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        """Handle received datagram."""
        if addr[0] != self.coordinator.host:
            _LOGGER.debug(
                "Ignoring datagram from unexpected source %s (expected %s)",
                addr[0],
                self.coordinator.host,
            )
            return
        _LOGGER.debug("Received %d bytes from %s, %s", len(data), addr, data)

        try:
            payload = powerhub_pb2.Payload()
            payload.ParseFromString(data)
        except DecodeError as err:
            _LOGGER.error("Failed to decode protobuf message: %s", err)

        # Update coordinator with new data
        if payload.HasField("sample"):
            _LOGGER.debug("Received sample data")
            self.coordinator.async_set_sample_data(payload.sample)
        elif payload.HasField("diagnostic"):
            _LOGGER.debug("Received diagnostic data")
            self.coordinator.async_set_diagnostic_data(payload.diagnostic)
        else:
            _LOGGER.warning("Received unknown payload type")

    def error_received(self, exc: Exception) -> None:
        """Handle error."""
        _LOGGER.error("UDP protocol error: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        """Handle connection lost."""
        if exc:
            _LOGGER.error("UDP connection lost: %s", exc)
        else:
            _LOGGER.debug("UDP connection closed")


class BitvisDataUpdateCoordinator(DataUpdateCoordinator[BitvisData]):
    """Coordinator to manage data updates from UDP packets."""

    def __init__(
        self, hass: HomeAssistant, config_entry: ConfigEntry, host: str, port: int
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=None,
            config_entry=config_entry,
        )
        self.host = host
        self.port = port
        self._transport: asyncio.DatagramTransport | None = None
        self._protocol: BitvisUDPProtocol | None = None
        self._watchdog_task: asyncio.Task | None = None
        self._unavailable_logged: bool = False
        self.data = BitvisData()

    async def async_start(self) -> None:
        """Start the UDP listener."""
        loop = asyncio.get_event_loop()

        self._transport, self._protocol = await loop.create_datagram_endpoint(
            lambda: BitvisUDPProtocol(self),
            local_addr=("0.0.0.0", self.port),
            reuse_port=True,
        )

        self._watchdog_task = asyncio.create_task(self._async_watchdog())

        _LOGGER.info("Started UDP listener on port %s", self.port)

    async def async_stop(self) -> None:
        """Stop the UDP listener."""
        if self._watchdog_task:
            self._watchdog_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._watchdog_task
            self._watchdog_task = None

        if self._transport:
            self._transport.close()
            self._transport = None

        _LOGGER.info("Stopped UDP listener")

    async def _async_watchdog(self) -> None:
        """Monitor for stale data and mark unavailable."""
        while True:
            await asyncio.sleep(WATCHDOG_INTERVAL.total_seconds())

            if self.data.timestamp:
                time_since_update = datetime.now() - self.data.timestamp
                if time_since_update > WATCHDOG_INTERVAL:
                    if not self._unavailable_logged:
                        _LOGGER.info(
                            "No data received for %s seconds, marking unavailable",
                            time_since_update.total_seconds(),
                        )
                        self._unavailable_logged = True
                    self.data = BitvisData()
                    self.last_update_success = False
                    self.async_update_listeners()

    @callback
    def async_set_sample_data(self, sample: HanPortSample) -> None:
        """Update sample data and notify listeners."""
        if self._unavailable_logged:
            _LOGGER.info("Device is back online")
            self._unavailable_logged = False
        self.data.sample = sample
        self.data.timestamp = datetime.now()
        self.last_update_success = True
        self.async_update_listeners()

    @callback
    def async_set_diagnostic_data(self, diagnostic: Diagnostic) -> None:
        """Update diagnostic data and notify listeners."""
        if self._unavailable_logged:
            _LOGGER.info("Device is back online")
            self._unavailable_logged = False
        self.data.diagnostic = diagnostic
        self.data.timestamp = datetime.now()

        # Extract device info if available
        if diagnostic.HasField("device_info"):
            device_info = diagnostic.device_info
            self.data.mac_address = device_info.mac_address.hex(sep=":")
            self.data.model_name = device_info.model_name
            self.data.sw_version = device_info.sw_version

        self.last_update_success = True
        self.async_update_listeners()

    async def _async_update_data(self) -> BitvisData:
        """Update data (not used for push-based updates)."""
        raise NotImplementedError

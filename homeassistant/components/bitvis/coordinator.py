"""Data coordinator for Bitvis Power Hub."""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime
import ipaddress
import logging

from bitvis_protobuf.listener import SharedListener
from bitvis_protobuf.parse import PayloadDiagnostic, PayloadSample
from bitvis_protobuf.utils import format_mac_address

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import DOMAIN, WATCHDOG_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass
class BitvisData:
    """Data structure for Bitvis measurements."""

    sample: PayloadSample | None = None
    diagnostic: PayloadDiagnostic | None = None
    timestamp: datetime | None = None
    mac_address: str | None = None
    model_name: str | None = None
    sw_version: str | None = None


class BitvisListenerRegistry:
    """Registry that manages one shared UDP listener per port.

    Stored at hass.data[DOMAIN]["listener_registry"] so all coordinators can
    look it up without duplicating state-management logic.
    """

    def __init__(self) -> None:
        """Initialize registry storage."""
        self._listeners: dict[int, SharedListener] = {}
        self._locks: dict[int, asyncio.Lock] = {}

    async def async_get_or_create(self, port: int) -> SharedListener:
        """Return the listener for *port*, creating and starting it if needed."""
        port_lock = self._locks.setdefault(port, asyncio.Lock())
        async with port_lock:
            if port not in self._listeners:
                listener = SharedListener()
                await listener.start(port)
                self._listeners[port] = listener
            return self._listeners[port]

    async def async_remove_if_unused(self, port: int) -> None:
        """Stop and remove the listener for *port* when no coordinators remain."""
        port_lock = self._locks.setdefault(port, asyncio.Lock())
        async with port_lock:
            listener = self._listeners.get(port)
            if listener is None or not listener.is_empty:
                return
            await listener.stop()
            del self._listeners[port]

    def get(self, port: int) -> SharedListener | None:
        """Return an existing listener for *port*, or None."""
        return self._listeners.get(port)

    def has_listener(self, port: int) -> bool:
        """Return True if a listener is already active on *port*."""
        return port in self._listeners


def async_get_listener_registry(hass: HomeAssistant) -> BitvisListenerRegistry:
    """Return (creating if needed) the Bitvis listener registry for this HA instance."""
    domain_data = hass.data.setdefault(DOMAIN, {})
    if "listener_registry" not in domain_data:
        domain_data["listener_registry"] = BitvisListenerRegistry()
    registry: BitvisListenerRegistry = domain_data["listener_registry"]
    return registry


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
        self._registered_ips: set[str] = set()
        self._watchdog_task: asyncio.Task[None] | None = None
        self._unavailable_logged: bool = False
        self.data = BitvisData()

    async def _async_setup(self) -> None:
        """Set up the coordinator by registering with the shared UDP listener."""
        try:
            self._registered_ips = await self._async_resolve_host()
            listener_registry = async_get_listener_registry(self.hass)
            listener = await listener_registry.async_get_or_create(self.port)
            listener.register(self._registered_ips, self._handle_payload)
        except (OSError, ValueError) as err:
            await self.async_stop()
            raise UpdateFailed(
                f"Failed to start UDP listener on port {self.port}"
            ) from err
        except RuntimeError as err:
            await self.async_stop()
            raise ConfigEntryError(
                f"Failed to start UDP listener on port {self.port}"
            ) from err

        self._watchdog_task = asyncio.create_task(self._async_watchdog())
        _LOGGER.info(
            "Registered coordinator on shared UDP listener for port %s", self.port
        )

    async def async_stop(self) -> None:
        """Unregister from the shared listener, stopping it when no longer needed."""
        if self._watchdog_task:
            self._watchdog_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._watchdog_task
            self._watchdog_task = None

        if domain_data := self.hass.data.get(DOMAIN):
            listener_registry = domain_data.get("listener_registry")
            if isinstance(listener_registry, BitvisListenerRegistry):
                if listener := listener_registry.get(self.port):
                    listener.unregister(self._registered_ips)
                    await listener_registry.async_remove_if_unused(self.port)

        self._registered_ips = set()
        _LOGGER.info(
            "Unregistered coordinator from shared UDP listener for port %s", self.port
        )

    async def _async_resolve_host(self) -> set[str]:
        """Resolve the configured host to a set of IP addresses.

        Only IP addresses are registered with the shared listener. If the host is
        not already an IP literal and cannot be resolved, treat this as a setup
        error so Home Assistant can retry the config entry later.
        """
        ips: set[str] = set()

        # If the configured host is already an IP address, always include it.
        try:
            ipaddress.ip_address(self.host)
        except ValueError:
            pass
        else:
            ips.add(self.host)

        loop = asyncio.get_running_loop()
        try:
            addrinfo = await loop.getaddrinfo(self.host, None)
        except OSError:
            _LOGGER.debug("Could not resolve host %s to IP addresses", self.host)
        else:
            for *_, sockaddr in addrinfo:
                ips.add(sockaddr[0])

        if not ips:
            raise UpdateFailed(
                f"Could not resolve Bitvis Power Hub host {self.host!r} to an IP address"
            )

        return ips

    @callback
    def _handle_payload(
        self,
        payload: PayloadSample | PayloadDiagnostic,
        addr: tuple[str, int],
    ) -> None:
        """Handle a parsed payload dispatched by the shared listener."""
        _LOGGER.debug("Received payload from %s", addr)
        if isinstance(payload, PayloadSample):
            self._handle_sample(payload)
        else:
            self._handle_diagnostic(payload)

    @callback
    def _handle_sample(self, payload: PayloadSample) -> None:
        """Update sample data and notify listeners."""
        if self._unavailable_logged:
            _LOGGER.info("Device is back online")
            self._unavailable_logged = False
        self.data.sample = payload
        self.data.timestamp = dt_util.utcnow()
        self.last_update_success = True
        self.async_update_listeners()

    @callback
    def _handle_diagnostic(self, payload: PayloadDiagnostic) -> None:
        """Update diagnostic data and notify listeners."""
        if self._unavailable_logged:
            _LOGGER.info("Device is back online")
            self._unavailable_logged = False
        self.data.diagnostic = payload
        self.data.timestamp = dt_util.utcnow()

        diagnostic = payload.diagnostic
        if diagnostic.HasField("device_info"):
            device_info = diagnostic.device_info
            self.data.mac_address = format_mac_address(device_info.mac_address)
            self.data.model_name = device_info.model_name
            self.data.sw_version = device_info.sw_version
        else:
            self.data.mac_address = None
            self.data.model_name = None
            self.data.sw_version = None

        self.last_update_success = True
        self.async_update_listeners()

    async def _async_watchdog(self) -> None:
        """Monitor for stale data and mark unavailable."""
        while True:
            await asyncio.sleep(WATCHDOG_INTERVAL.total_seconds())

            if self.data.timestamp:
                time_since_update = dt_util.utcnow() - self.data.timestamp
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

    async def _async_update_data(self) -> BitvisData:
        """Return current data (updates are push-based via UDP datagrams)."""
        return self.data

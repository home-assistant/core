"""Data coordinator for Bitvis Power Hub."""

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from bitvis_protobuf.listener import SharedListener
from bitvis_protobuf.parse import PayloadDiagnostic, PayloadSample
from bitvis_protobuf.utils import async_resolve_host, format_mac_address

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.variance import ignore_variance

from .const import DATA_LISTENER_REGISTRY, DOMAIN, WATCHDOG_INTERVAL

_LOGGER = logging.getLogger(__name__)

type BitvisConfigEntry = ConfigEntry[BitvisDataUpdateCoordinator]


def _uptime_to_boot_time(uptime_s: int) -> datetime:
    """Convert uptime in seconds to an absolute boot datetime."""
    return dt_util.utcnow().replace(microsecond=0) - timedelta(seconds=uptime_s)


@dataclass
class BitvisData:
    """Data structure for Bitvis measurements."""

    sample: PayloadSample | None = None
    diagnostic: PayloadDiagnostic | None = None
    last_sample_timestamp: datetime | None = None
    mac_address: str | None = None
    model_name: str | None = None
    sw_version: str | None = None
    boot_time: datetime | None = None


class BitvisListenerRegistry:
    """Registry that manages one shared UDP listener per port.

    Stored at hass.data[DATA_LISTENER_REGISTRY] so all coordinators can
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
    if DATA_LISTENER_REGISTRY not in hass.data:
        hass.data[DATA_LISTENER_REGISTRY] = BitvisListenerRegistry()
    return hass.data[DATA_LISTENER_REGISTRY]


class BitvisDataUpdateCoordinator(DataUpdateCoordinator[BitvisData]):
    """Coordinator to manage data updates from UDP packets."""

    def __init__(
        self, hass: HomeAssistant, config_entry: BitvisConfigEntry, host: str, port: int
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
        self._stable_boot_time = ignore_variance(
            _uptime_to_boot_time, timedelta(minutes=5)
        )
        self.data = BitvisData()

    async def _async_setup(self) -> None:
        """Set up the coordinator by registering with the shared UDP listener."""
        try:
            self._registered_ips = await async_resolve_host(self.host)
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

        assert self.config_entry is not None
        self._watchdog_task = self.config_entry.async_create_background_task(
            self.hass,
            self._async_watchdog(),
            f"{DOMAIN} watchdog",
        )

    async def async_stop(self) -> None:
        """Unregister from the shared listener, stopping it when no longer needed."""
        if self._watchdog_task:
            self._watchdog_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._watchdog_task
            self._watchdog_task = None

        if listener_registry := self.hass.data.get(DATA_LISTENER_REGISTRY):
            if listener := listener_registry.get(self.port):
                listener.unregister(self._registered_ips)
                await listener_registry.async_remove_if_unused(self.port)

        self._registered_ips = set()
        _LOGGER.debug(
            "Unregistered coordinator from shared UDP listener for port %s", self.port
        )

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
        self.data.last_sample_timestamp = dt_util.utcnow()
        self.last_update_success = True
        self.async_update_listeners()

    @callback
    def _handle_diagnostic(self, payload: PayloadDiagnostic) -> None:
        """Update diagnostic data and notify listeners."""
        self.data.diagnostic = payload
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
        self.data.boot_time = self._stable_boot_time(diagnostic.uptime_s)

        self.async_update_listeners()

    async def _async_watchdog(self) -> None:
        """Monitor for stale data and mark unavailable."""
        while True:
            await asyncio.sleep(WATCHDOG_INTERVAL.total_seconds())

            if not self.data.last_sample_timestamp:
                continue

            time_since_update = dt_util.utcnow() - self.data.last_sample_timestamp
            if time_since_update < WATCHDOG_INTERVAL:
                continue

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

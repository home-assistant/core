"""Data coordinator for Bitvis Power Hub."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import override

from bitvis_protobuf.listener import FilterMac, SharedListener
from bitvis_protobuf.parse import PayloadDiagnostic, PayloadSample
from bitvis_protobuf.powerhub_pb2 import Diagnostic

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.util.variance import ignore_variance

from .const import DATA_LISTENER_REGISTRY, DOMAIN, MODEL_NAME

_LOGGER = logging.getLogger(__name__)

type BitvisConfigEntry = ConfigEntry[BitvisDataUpdateCoordinator]


def _uptime_to_boot_time(uptime_s: int) -> datetime:
    """Convert uptime in seconds to an absolute boot datetime."""
    return dt_util.utcnow().replace(microsecond=0) - timedelta(seconds=uptime_s)


@dataclass(kw_only=True)
class BitvisData:
    """Data structure for Bitvis measurements."""

    sample: PayloadSample | None = None
    diagnostic: PayloadDiagnostic | None = None
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

    config_entry: BitvisConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: BitvisConfigEntry,
        host: str,
        port: int,
        mac_address: str,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=config_entry,
        )
        self.host = host
        self.port = port
        self.mac_address = mac_address
        self._filter = FilterMac(mac_address)
        self._registered = False
        self._stable_boot_time = ignore_variance(
            _uptime_to_boot_time, timedelta(minutes=5)
        )
        self.data = BitvisData()

    @override
    async def _async_setup(self) -> None:
        """Set up the coordinator by registering with the shared UDP listener."""
        try:
            listener_registry = async_get_listener_registry(self.hass)
            listener = await listener_registry.async_get_or_create(self.port)
            listener.register(self._filter, self._handle_payload)
            self._registered = True
        except OSError as err:
            raise UpdateFailed(
                f"Failed to start UDP listener on port {self.port}"
            ) from err
        except RuntimeError as err:
            raise ConfigEntryError(
                f"Failed to start UDP listener on port {self.port}"
            ) from err

    async def async_stop(self) -> None:
        """Unregister from the shared listener, stopping it when no longer needed."""
        if not self._registered:
            return

        if listener_registry := self.hass.data.get(DATA_LISTENER_REGISTRY):
            if listener := listener_registry.get(self.port):
                listener.unregister(self._filter)
                await listener_registry.async_remove_if_unused(self.port)

        self._registered = False
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
        self.data.sample = payload
        self.async_set_updated_data(self.data)

    @callback
    def _handle_diagnostic(self, payload: PayloadDiagnostic) -> None:
        """Update diagnostic data and notify listeners."""
        self.data.diagnostic = payload
        diagnostic = payload.diagnostic
        self._update_device_registry(diagnostic)
        self.data.boot_time = self._stable_boot_time(diagnostic.uptime_s)

        self.async_set_updated_data(self.data)

    @callback
    def _update_device_registry(self, diagnostic: Diagnostic) -> None:
        """Update device registry with model and firmware from diagnostics."""
        device_reg = dr.async_get(self.hass)
        if not (
            device := device_reg.async_get_device_by_identifier(
                (DOMAIN, self.mac_address), self.config_entry.entry_id
            )
        ):
            return

        if diagnostic.HasField("device_info"):
            device_info = diagnostic.device_info
            model = device_info.model_name or MODEL_NAME
            sw_version = device_info.sw_version or None
        else:
            model = MODEL_NAME
            sw_version = None

        if device.model != model or device.sw_version != sw_version:
            device_reg.async_update_device(
                device.id, model=model, sw_version=sw_version
            )

    @override
    async def _async_update_data(self) -> BitvisData:
        """Return current data (updates are push-based via UDP datagrams)."""
        return self.data

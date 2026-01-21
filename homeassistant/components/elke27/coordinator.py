"""Data update coordinator for the Elke27 integration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
import contextlib
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN
from .hub import Elke27Hub

try:  # pragma: no cover - optional import for local test runs without the lib.
    from elke27_lib.events import (
        ConnectionStateChanged,
        CsmSnapshotUpdated,
        DomainCsmChanged,
        TableCsmChanged,
        ZoneStatusUpdated,
    )
except ModuleNotFoundError:  # pragma: no cover - handled via class name fallback.
    ConnectionStateChanged = None
    CsmSnapshotUpdated = None
    DomainCsmChanged = None
    TableCsmChanged = None
    ZoneStatusUpdated = None

_LOGGER = logging.getLogger(__name__)

type PanelSnapshot = Any


class Elke27DataUpdateCoordinator(DataUpdateCoordinator[PanelSnapshot]):
    """Coordinate Elke27 snapshot updates and CSM refreshes."""

    def __init__(
        self,
        hass: HomeAssistant,
        hub: Elke27Hub,
        entry: ConfigEntry,
        *,
        debounce_seconds: float = 0.3,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry)
        self._hub = hub
        self._debounce_seconds = debounce_seconds
        self._pending_domains: set[str] = set()
        self._refresh_lock = asyncio.Lock()
        self._debounce_task: asyncio.Task[None] | None = None
        self._unsubscribe: Callable[[], None] | None = None

    async def async_start(self) -> None:
        """Subscribe to hub events and seed snapshot data."""
        if self._unsubscribe is not None:
            self._unsubscribe()
        self._unsubscribe = self._hub.subscribe_typed(self._handle_event)
        self._set_snapshot(self._hub.get_snapshot())

    async def async_stop(self) -> None:
        """Stop coordinating updates and clean up resources."""
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        if self._debounce_task is not None:
            self._debounce_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._debounce_task
            self._debounce_task = None

    async def async_refresh_now(self) -> None:
        """Perform a full CSM refresh and update the snapshot."""
        await self._hub.refresh_csm()
        self._set_snapshot(self._hub.get_snapshot())

    def _handle_event(self, event: Any) -> None:
        """Handle hub events on the Home Assistant event loop."""
        self.hass.loop.call_soon_threadsafe(self._process_event, event)

    @callback
    def _process_event(self, event: Any) -> None:
        """Process an event from the hub."""
        if _is_event(event, ZoneStatusUpdated, "ZoneStatusUpdated"):
            _LOGGER.debug(
                "Zone status event received: zone_id=%s changed_fields=%s",
                getattr(event, "zone_id", None),
                getattr(event, "changed_fields", None),
            )
        if _is_event(event, ConnectionStateChanged, "ConnectionStateChanged"):
            if getattr(event, "connected", False):
                self.hass.async_create_task(self.async_refresh_now())
            return
        if _is_event(event, CsmSnapshotUpdated, "CsmSnapshotUpdated"):
            self._set_snapshot(self._hub.get_snapshot())
            return
        if _is_event(event, DomainCsmChanged, "DomainCsmChanged"):
            domain = getattr(event, "domain", None)
            if domain:
                self._queue_domain_refresh({str(domain)})
            return
        if _is_event(event, TableCsmChanged, "TableCsmChanged"):
            domain = getattr(event, "domain", None)
            if domain:
                self._queue_domain_refresh({str(domain)})
            return
        self._set_snapshot(self._hub.get_snapshot())

    def _queue_domain_refresh(self, domains: Iterable[str]) -> None:
        """Queue a refresh for the given domains and debounce updates."""
        self._pending_domains.update(_normalize_domains(domains))
        if self._debounce_task is None or self._debounce_task.done():
            self._debounce_task = self.hass.async_create_task(
                self._async_debounced_refresh()
            )

    async def _async_debounced_refresh(self) -> None:
        """Refresh pending domains after a short debounce delay."""
        await asyncio.sleep(self._debounce_seconds)
        async with self._refresh_lock:
            while self._pending_domains:
                domains = set(self._pending_domains)
                self._pending_domains.clear()
                results = await asyncio.gather(
                    *(self._hub.refresh_domain_config(domain) for domain in domains),
                    return_exceptions=True,
                )
                for domain, result in zip(domains, results, strict=True):
                    if isinstance(result, Exception):
                        _LOGGER.debug(
                            "Domain refresh failed for %s: %s", domain, result
                        )
        self._set_snapshot(self._hub.get_snapshot())

    def _set_snapshot(self, snapshot: PanelSnapshot | None) -> None:
        """Update coordinator data and track snapshot version."""
        self.async_set_updated_data(snapshot)


def _is_event(event: Any, klass: type[Any] | None, name: str) -> bool:
    if klass is not None:
        return isinstance(event, klass)
    return event.__class__.__name__ == name


def _normalize_domains(domains: Iterable[str] | str | None) -> set[str]:
    if domains is None:
        return set()
    if isinstance(domains, str):
        return {domains}
    return {str(domain) for domain in domains if domain}

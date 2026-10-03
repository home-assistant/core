"""Coordinator: aiolanbon only. Poll revision; apply WebSocket events in memory."""

import asyncio
from dataclasses import replace
from datetime import timedelta
import logging
from typing import TYPE_CHECKING, override

from aiolanbon import (
    LanbonAuthError,
    LanbonClient,
    LanbonConnectionError,
    LanbonError,
    LanbonEventsUnsupportedError,
    LanbonTimeoutError,
    SnapshotRefresh,
)
from aiolanbon.models import DeviceSnapshot, Event, GatewayInfo

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

if TYPE_CHECKING:
    from . import LanbonConfigEntry

_LOGGER = logging.getLogger(__name__)
_POLL = timedelta(seconds=15)


def _patch_state_changed(snap: DeviceSnapshot, event: Event) -> DeviceSnapshot | None:
    """Apply a state_changed event onto a snapshot copy."""
    if event.type != "state_changed" or not event.revision:
        return None
    if not event.device_id or not event.component_id or not event.state:
        return None
    device = snap.device(event.device_id)
    if device is None:
        return None
    component = device.component(event.component_id)
    if component is None:
        return None
    new_comp = replace(component, state=dict(event.state))
    new_comps = tuple(
        new_comp if item.id == component.id else item for item in device.components
    )
    new_dev = replace(device, components=new_comps)
    new_devs = tuple(new_dev if item.id == device.id else item for item in snap.devices)
    return replace(snap, devices=new_devs, revision=str(event.revision))


def _patch_availability(snap: DeviceSnapshot, event: Event) -> DeviceSnapshot | None:
    """Apply an availability_changed event onto a snapshot copy."""
    if event.type != "availability_changed" or not event.revision:
        return None
    if not event.device_id or event.online is None:
        return None
    device = snap.device(event.device_id)
    if device is None:
        return None
    new_dev = replace(device, online=bool(event.online))
    new_devs = tuple(new_dev if item.id == device.id else item for item in snap.devices)
    return replace(snap, devices=new_devs, revision=str(event.revision))


class LanbonCoordinator(DataUpdateCoordinator[DeviceSnapshot]):
    """Fetch LOIP device snapshot and optionally listen for events."""

    config_entry: LanbonConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: LanbonConfigEntry,
        client: LanbonClient,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=_POLL,
        )
        self.client = client
        self.gateway_verified = False
        self.info: GatewayInfo | None = None
        self._etag: str | None = None
        self._snapshot_events: (
            dict[tuple[str, str | None, str | None], Event] | None
        ) = None
        self._force_snapshot = False
        self._events_task: asyncio.Task | None = None
        self._use_ws = False

    @override
    async def _async_setup(self) -> None:
        """Read gateway info and whether events WebSocket is advertised."""
        try:
            info = await self.client.get_info()
        except LanbonAuthError as err:
            raise ConfigEntryAuthFailed("unauthorized") from err
        except (
            LanbonConnectionError,
            LanbonTimeoutError,
            LanbonError,
        ) as err:
            raise UpdateFailed(type(err).__name__) from err
        if not info.api_enabled:
            self.gateway_verified = False
            self.info = None
            self._etag = None
            raise UpdateFailed("Open Integration is disabled")
        self._verify_gateway(info.gateway_id)
        self.info = info
        self._use_ws = bool(info.events_websocket)

    def _verify_gateway(self, gateway_id: str) -> None:
        """Reject data belonging to a different configured gateway."""
        if not gateway_id or gateway_id != self.config_entry.unique_id:
            self.gateway_verified = False
            self.info = None
            self._etag = None
            raise UpdateFailed("Gateway identity does not match the configured gateway")

    @override
    async def _async_update_data(self) -> DeviceSnapshot:
        """GET /devices, using If-None-Match when a revision is already known."""
        events: dict[tuple[str, str | None, str | None], Event] = {}
        try:
            if self.info is None:
                await self._async_setup()
            if self._force_snapshot:
                self._etag = None
                self._force_snapshot = False
            # Retain only the latest event per field during this request.
            self._snapshot_events = events
            snap = await self.client.get_devices(if_none_match=self._etag)
        except LanbonAuthError as err:
            raise ConfigEntryAuthFailed("unauthorized") from err
        except (
            LanbonConnectionError,
            LanbonTimeoutError,
            LanbonError,
        ) as err:
            raise UpdateFailed(type(err).__name__) from err
        finally:
            self._snapshot_events = None
        if snap is None:
            if self.data is None or not self.gateway_verified:
                raise UpdateFailed("empty snapshot")
            return self.data
        self._verify_gateway(snap.gateway_id)
        self.gateway_verified = True
        self._etag = None if events else snap.revision
        for event in events.values():
            if event.type == "state_changed":
                patched = _patch_state_changed(snap, event)
            else:
                patched = _patch_availability(snap, event)
            # The full snapshot owns topology; events cannot resurrect removals.
            if patched is not None:
                snap = patched
        return snap

    @override
    async def async_config_entry_first_refresh(self) -> None:
        """Refresh once, then start the events task when the gateway supports it."""
        await super().async_config_entry_first_refresh()
        if self._use_ws:
            self._events_task = self.config_entry.async_create_background_task(
                self.hass, self._events_loop(), name="lanbon-loip-events"
            )

    def _apply_event(self, event: Event) -> bool:
        """Patch coordinator data from a WS event. False → caller must GET /devices."""
        if self.data is None or not self.gateway_verified:
            return False
        if event.type == "state_changed":
            patched = _patch_state_changed(self.data, event)
        elif event.type == "availability_changed":
            patched = _patch_availability(self.data, event)
        elif event.type in {"button_pressed", "scene_activated", "command_result"}:
            return True
        else:
            return False
        if patched is None:
            return False
        if self._snapshot_events is not None:
            key = (
                event.type,
                event.device_id,
                event.component_id if event.type == "state_changed" else None,
            )
            self._snapshot_events.pop(key, None)
            self._snapshot_events[key] = event
        # An event updates only part of the snapshot, not a complete HTTP ETag.
        self._etag = None
        # Partial updates must not postpone polling or clear a full-refresh error.
        self.data = patched
        self.async_update_listeners()
        return True

    async def _events_loop(self) -> None:
        try:
            async for item in self.client.listen():
                if isinstance(item, SnapshotRefresh):
                    self._force_snapshot = True
                elif self._apply_event(item):
                    continue
                else:
                    self._force_snapshot = True
                # Wait for the HTTP response even during debounce cooldown.
                await self.async_refresh()
                if not self.last_update_success:
                    self._use_ws = False
                    return
        except LanbonEventsUnsupportedError:
            _LOGGER.debug("events websocket unsupported; polling /devices")
            self._use_ws = False
        except asyncio.CancelledError:
            raise
        except (
            LanbonAuthError,
            LanbonConnectionError,
            LanbonTimeoutError,
            LanbonError,
            OSError,
        ):
            _LOGGER.debug("events loop ended; stay on polling")
            self._use_ws = False

    def async_on_unload(self) -> None:
        """Cancel the events task."""
        if self._events_task and not self._events_task.done():
            self._events_task.cancel()

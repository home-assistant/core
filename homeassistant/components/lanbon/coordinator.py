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
        self.info: GatewayInfo | None = None
        self._etag: str | None = None
        self._events_task: asyncio.Task | None = None
        self._use_ws = False
        self._refresh_dirty = False
        self._refresh_task: asyncio.Task | None = None

    @override
    async def _async_setup(self) -> None:
        """Read gateway info and whether events WebSocket is advertised."""
        try:
            self.info = await self.client.get_info()
        except (
            LanbonAuthError,
            LanbonConnectionError,
            LanbonTimeoutError,
            LanbonError,
        ) as err:
            raise UpdateFailed(type(err).__name__) from err
        self._use_ws = bool(self.info.events_websocket)

    @override
    async def _async_update_data(self) -> DeviceSnapshot:
        """GET /devices, using If-None-Match when a revision is already known."""
        try:
            if self.info is None:
                await self._async_setup()
            snap = await self.client.get_devices(if_none_match=self._etag)
        except (
            LanbonAuthError,
            LanbonConnectionError,
            LanbonTimeoutError,
            LanbonError,
        ) as err:
            raise UpdateFailed(type(err).__name__) from err
        if snap is None:
            if self.data is None:
                raise UpdateFailed("empty snapshot")
            return self.data
        self._etag = snap.revision
        return snap

    @override
    async def async_config_entry_first_refresh(self) -> None:
        """Refresh once, then start the events task when the gateway supports it."""
        await super().async_config_entry_first_refresh()
        if self._use_ws:
            self._events_task = self.config_entry.async_create_background_task(
                self.hass, self._events_loop(), name="lanbon-loip-events"
            )

    def _request_snapshot(self) -> None:
        """Clear ETag and GET /devices. Coalesce overlapping SnapshotRefresh."""
        self._etag = None
        self._refresh_dirty = True
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.get_running_loop().create_task(
                self._drain_snapshot_refresh()
            )

    async def _drain_snapshot_refresh(self) -> None:
        try:
            while self._refresh_dirty:
                self._refresh_dirty = False
                await self.async_request_refresh()
        finally:
            self._refresh_task = None

    async def _await_snapshot_refresh(self) -> None:
        task = self._refresh_task
        if task is not None:
            await task

    def _apply_event(self, event: Event) -> bool:
        """Patch coordinator data from a WS event. False → caller must GET /devices."""
        if self.data is None:
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
        self._etag = patched.revision
        self.async_set_updated_data(patched)
        return True

    async def _events_loop(self) -> None:
        try:
            async for item in self.client.listen():
                if isinstance(item, SnapshotRefresh):
                    self._request_snapshot()
                    continue
                if self._apply_event(item):
                    continue
                self._request_snapshot()
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
        finally:
            await self._await_snapshot_refresh()

    def async_on_unload(self) -> None:
        """Cancel the events task."""
        if self._events_task and not self._events_task.done():
            self._events_task.cancel()

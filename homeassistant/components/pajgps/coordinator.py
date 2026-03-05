"""
DataUpdateCoordinator for the PAJ GPS integration.

Responsibilities:
- Own the single PajGpsApi instance for the lifetime of a config entry.
- Drive three update tiers at different frequencies:
    Tier 1 — device list       every DEVICES_INTERVAL seconds
    Tier 2 — positions+sensors every POSITIONS_INTERVAL seconds
    Tier 3 — notifications     every NOTIFICATIONS_INTERVAL seconds
- Delegate per-device call serialization to DeviceRequestQueue (device_queue.py).
- Delegate elevation fetching and device-copy helpers to coordinator_utils.py.
- Push CoordinatorData snapshots to entities as soon as each response arrives.
"""
from __future__ import annotations

import asyncio
import dataclasses
import logging
import time
import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from pajgps_api import PajGpsApi
from pajgps_api.pajgps_api_error import PajGpsApiError, AuthenticationError, TokenRefreshError
from pajgps_api.models.trackpoint import TrackPoint
from pajgps_api.models.notification import Notification

from .const import (
    DOMAIN,
    VERSION,
    DEVICES_INTERVAL,
    POSITIONS_INTERVAL,
    NOTIFICATIONS_INTERVAL,
    MIN_ELEVATION_UPDATE_DELAY,
    MIN_ELEVATION_DISTANCE,
    ALERT_TYPE_TO_DEVICE_FIELD,
)
from .coordinator_data import CoordinatorData
from .coordinator_utils import fetch_elevation as _fetch_elevation_http, apply_alert_flag
from .device_queue import DeviceRequestQueue

# Re-export so existing imports (tests, platform files) keep working unchanged.
__all__ = ["CoordinatorData", "DeviceRequestQueue", "PajGpsCoordinator", "apply_alert_flag"]

# Legacy alias used in tests that import _apply_alert_flag from this module
_apply_alert_flag = apply_alert_flag

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PajGpsCoordinator — main coordinator
# ---------------------------------------------------------------------------

class PajGpsCoordinator(DataUpdateCoordinator[CoordinatorData]):
    """
    Coordinator for the PAJ GPS integration.

    Drives three update tiers at different rates and pushes partial data
    snapshots to entities as soon as each response arrives.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry_data: dict,
        websession: aiohttp.ClientSession | None = None,
    ) -> None:
        """Initialize the coordinator from config-entry data."""
        from datetime import timedelta
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            # Use the fastest tier as the HA poll interval so HA calls us often
            # enough; we gate each tier internally with our own timestamps.
            update_interval=timedelta(seconds=NOTIFICATIONS_INTERVAL),
            config_entry=None,  # not used, but required by signature
        )

        self.api = PajGpsApi(
            email=entry_data["email"],
            password=entry_data["password"],
            websession=websession,
        )
        self._entry_data = entry_data
        self._queue = DeviceRequestQueue()

        # Tier timestamps — initialized to 0 so every tier fires on first call
        self._last_devices_fetch: float = 0.0
        self._last_positions_fetch: float = 0.0
        self._last_notifications_fetch: float = 0.0

        # Elevation state per device
        self._last_elevation_fetch: dict[int, float] = {}
        self._last_elevation_pos: dict[int, tuple[float, float]] = {}
        self._elevation_tasks: set[asyncio.Task] = set()

        # Flag to distinguish first call from subsequent ones
        self._initial_refresh_done: bool = False

        # Snapshot starts empty; entities must handle None gracefully until first refresh
        self.data = CoordinatorData()

    # ------------------------------------------------------------------
    # HA entry point
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> CoordinatorData:
        """
        Called by HA on every update_interval tick.

        First call: runs all three tiers sequentially and returns a fully
        populated snapshot (so async_config_entry_first_refresh() succeeds).

        Subsequent calls: fires due tiers as independent background tasks and
        returns the current snapshot immediately; entities receive push updates
        via async_set_updated_data() as each task completes.
        """
        try:
            await self.api.login()
        except (AuthenticationError, TokenRefreshError) as exc:
            raise UpdateFailed(f"PAJ GPS authentication failed: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            raise UpdateFailed(f"PAJ GPS connection error: {exc}") from exc

        if not self._initial_refresh_done:
            await self._run_devices_tier()
            await self._run_positions_tier()
            await self._run_notifications_tier()
            self._initial_refresh_done = True
            return self.data

        now = time.monotonic()

        if now - self._last_devices_fetch >= DEVICES_INTERVAL:
            self.hass.async_create_task(self._run_devices_tier())

        if now - self._last_positions_fetch >= POSITIONS_INTERVAL:
            self.hass.async_create_task(self._run_positions_tier())

        if now - self._last_notifications_fetch >= NOTIFICATIONS_INTERVAL:
            self.hass.async_create_task(self._run_notifications_tier())

        return self.data

    # ------------------------------------------------------------------
    # Tier 1 — device list
    # ------------------------------------------------------------------

    async def _run_devices_tier(self) -> None:
        """Fetch the full device list and push an updated snapshot."""
        self._last_devices_fetch = time.monotonic()
        try:
            devices = await self.api.get_devices()
        except (PajGpsApiError, Exception) as exc:  # noqa: BLE001
            _LOGGER.warning("Failed to fetch device list: %s", exc)
            return

        new_data = dataclasses.replace(self.data, devices=devices)
        self.async_set_updated_data(new_data)

    # ------------------------------------------------------------------
    # Tier 2 — positions + sensors (+ elevation side-effects)
    # ------------------------------------------------------------------

    async def _run_positions_tier(self) -> None:
        """
        Fetch all positions in one bulk request, then enqueue per-device
        sensor requests.  Elevation tasks are launched as needed.
        """
        self._last_positions_fetch = time.monotonic()
        device_ids = [d.id for d in self.data.devices if d.id is not None]
        if not device_ids:
            return

        # --- bulk positions ---
        try:
            track_points = await self.api.get_all_last_positions(device_ids)
        except (PajGpsApiError, Exception) as exc:  # noqa: BLE001
            _LOGGER.warning("Failed to fetch positions: %s", exc)
            return

        new_positions = {tp.iddevice: tp for tp in track_points if tp.iddevice is not None}
        new_data = dataclasses.replace(self.data, positions=new_positions)
        self.async_set_updated_data(new_data)

        # --- elevation side-effects ---
        self._schedule_elevation_tasks(new_positions)

        # --- per-device sensor requests ---
        sensor_futures = {
            device_id: await self._queue.enqueue(
                device_id,
                "sensor",
                lambda did=device_id: self.api.get_last_sensor_data(did),
            )
            for device_id in device_ids
        }

        async def _collect_sensor(device_id: int, fut: asyncio.Future) -> None:
            try:
                sensor = await fut
                if sensor is None or sensor == []:
                    return
                new_sensors = dict(self.data.sensor_data)
                new_sensors[device_id] = sensor
                self.async_set_updated_data(
                    dataclasses.replace(self.data, sensor_data=new_sensors)
                )
            except Exception as exc:  # noqa: BLE001
                # The pajgps-api library raises "Unexpected response format: []" when the
                # device has no sensor hardware and the endpoint returns an empty array.
                # This is expected for basic trackers — log at DEBUG, not WARNING.
                if "Unexpected response format" in str(exc):
                    _LOGGER.debug("No sensor data for device %s (device may lack sensors)", device_id)
                else:
                    _LOGGER.warning("Failed to fetch sensor data for device %s: %s", device_id, exc)

        await asyncio.gather(
            *[_collect_sensor(did, fut) for did, fut in sensor_futures.items()],
            return_exceptions=True,
        )

    def _schedule_elevation_tasks(self, new_positions: dict[int, TrackPoint]) -> None:
        """Launch elevation fetch tasks for devices that have moved enough."""
        fetch_elevation = self._entry_data.get("fetch_elevation", False)
        if not fetch_elevation:
            return

        now = time.monotonic()
        for device_id, tp in new_positions.items():
            if tp.lat is None or tp.lng is None:
                continue

            new_lat, new_lng = float(tp.lat), float(tp.lng)
            elevation_missing = self.data.elevations.get(device_id) is None
            last_pos = self._last_elevation_pos.get(device_id)
            time_elapsed = (
                now - self._last_elevation_fetch.get(device_id, 0.0)
            ) >= MIN_ELEVATION_UPDATE_DELAY

            if elevation_missing:
                should_fetch = True
            elif last_pos is not None and time_elapsed:
                moved = (
                    abs(new_lat - last_pos[0]) >= MIN_ELEVATION_DISTANCE
                    or abs(new_lng - last_pos[1]) >= MIN_ELEVATION_DISTANCE
                )
                should_fetch = moved
            else:
                should_fetch = False

            if should_fetch:
                self._last_elevation_fetch[device_id] = now
                self._last_elevation_pos[device_id] = (new_lat, new_lng)
                task = self.hass.async_create_task(
                    self._fetch_elevation_for(device_id, new_lat, new_lng)
                )
                self._elevation_tasks.add(task)
                task.add_done_callback(self._elevation_tasks.discard)

    async def _fetch_elevation_for(self, device_id: int, lat: float, lng: float) -> None:
        """Fetch elevation and push an updated snapshot on success."""
        elevation = await self._fetch_elevation(lat, lng)
        if elevation is None:
            return
        new_elevations = dict(self.data.elevations)
        new_elevations[device_id] = round(elevation)
        self.async_set_updated_data(
            dataclasses.replace(self.data, elevations=new_elevations)
        )

    async def _fetch_elevation(self, lat: float, lng: float) -> float | None:
        """Delegate to coordinator_utils.fetch_elevation (keeps elevation logic low-level)."""
        return await _fetch_elevation_http(lat, lng)

    # ------------------------------------------------------------------
    # Tier 3 — notifications
    # ------------------------------------------------------------------

    async def _run_notifications_tier(self) -> None:
        """
        Enqueue a notifications fetch for each device and push updates as
        each response arrives.  Optionally marks notifications as read.
        """
        self._last_notifications_fetch = time.monotonic()
        device_ids = [d.id for d in self.data.devices if d.id is not None]
        if not device_ids:
            return

        notification_futures = {
            device_id: await self._queue.enqueue(
                device_id,
                "notifications",
                lambda did=device_id: self.api.get_device_notifications(did, is_read=0),
            )
            for device_id in device_ids
        }

        mark_as_read = self._entry_data.get("mark_alerts_as_read", False)

        async def _collect_notifications(device_id: int, fut: asyncio.Future) -> None:
            try:
                raw_notifications: list[Notification] = await fut
                if raw_notifications is None:
                    return
                unread = [n for n in raw_notifications if n.isread == 0]
                new_notifications = dict(self.data.notifications)
                new_notifications[device_id] = unread
                self.async_set_updated_data(
                    dataclasses.replace(self.data, notifications=new_notifications)
                )
                if mark_as_read and unread:
                    self.hass.async_create_task(
                        self.api.mark_notifications_read_by_device(device_id, is_read=1)
                    )
            except Exception as exc:  # noqa: BLE001
                _LOGGER.warning(
                    "Failed to fetch notifications for device %s: %s", device_id, exc
                )

        await asyncio.gather(
            *[_collect_notifications(did, fut) for did, fut in notification_futures.items()],
            return_exceptions=True,
        )

    # ------------------------------------------------------------------
    # Write path — alert toggle (called directly from switch.py)
    # ------------------------------------------------------------------

    async def async_update_alert_state(
        self, device_id: int, alert_type: int, enabled: bool
    ) -> None:
        """
        Immediately send a PUT to PAJ GPS to enable/disable an alert, then
        optimistically update the local snapshot.

        Does NOT trigger a coordinator refresh — the next scheduled device-tier
        poll will confirm the server-side state.
        """
        field = ALERT_TYPE_TO_DEVICE_FIELD.get(alert_type)
        if field is None:
            _LOGGER.error("Unknown alert_type %s — cannot update device", alert_type)
            return

        try:
            await self.api.update_device(device_id, **{field: 1 if enabled else 0})
        except (PajGpsApiError, Exception) as exc:  # noqa: BLE001
            _LOGGER.error(
                "Failed to update alert %s for device %s: %s", alert_type, device_id, exc
            )
            return

        # Optimistic update: reflect the new state immediately in the snapshot
        updated_devices = [
            _apply_alert_flag(d, alert_type, enabled) if d.id == device_id else d
            for d in self.data.devices
        ]
        self.async_set_updated_data(
            dataclasses.replace(self.data, devices=updated_devices)
        )

    # ------------------------------------------------------------------
    # Entity helper — device info dict
    # ------------------------------------------------------------------

    def get_device_info(self, device_id: int) -> dict | None:
        """Return the HA DeviceInfo dict for the given device_id."""
        for device in self.data.devices:
            if device.id == device_id:
                return {
                    "identifiers": {(DOMAIN, f"{self._entry_data['guid']}_{device_id}")},
                    "name": device.name or f"PAJ GPS {device_id}",
                    "manufacturer": "PAJ GPS",
                    "model": (device.device_models[0]["model"] if device.device_models else None) or "Unknown",
                    "sw_version": VERSION,
                }
        return None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_shutdown(self) -> None:
        """Clean up all resources owned by this coordinator."""
        await self._queue.shutdown()
        await self.api.close()
        for task in list(self._elevation_tasks):
            task.cancel()
        if self._elevation_tasks:
            await asyncio.gather(*self._elevation_tasks, return_exceptions=True)
        self._elevation_tasks.clear()

    @property
    def entry_data(self):
        return self._entry_data

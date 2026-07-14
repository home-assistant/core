"""Bosch Smart Home Camera — Image Platform.

Creates one `image` entity per camera:
  image.bosch_<slugified_name>_last_snapshot

The entity serves the latest persisted snapshot JPEG from disk
(.storage/bosch_shc_camera/snapshots/{cam_id}.jpg).

Why a separate image entity instead of relying on camera.* snapshots?
WKWebView (iOS Companion App) applies heuristic disk-caching to HA's
CameraImageView responses because they carry no Cache-Control header.
Opening the app shows yesterday's stale snapshot for up to 5 seconds.
An image entity changes its signed URL on every `image_last_updated`
state-change, forcing WKWebView to use a fresh cache key — no stale
frames on cold open.

Requires `enable_snapshots=True` (same gate as the camera platform).
"""

from __future__ import annotations

import logging

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import (  # type: ignore[attr-defined]
    DOMAIN,
    BoschCameraConfigEntry,
    BoschCameraCoordinator,
    get_options,
)
from .models import get_display_name
from .snapshot_store import load_snapshot

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one image entity per discovered Bosch camera."""
    opts = get_options(config_entry)
    if not opts.get("enable_snapshots", True):
        _LOGGER.debug("Camera snapshots disabled — skipping image platform")
        return

    coordinator: BoschCameraCoordinator = config_entry.runtime_data
    entities = [
        BoschCameraLastSnapshotImage(hass, coordinator, cam_id, config_entry)
        for cam_id in coordinator.data
    ]
    async_add_entities(entities, update_before_add=False)


class BoschCameraLastSnapshotImage(ImageEntity):  # type: ignore[misc]  # HA base class is untyped (no py.typed) → Any
    """Image entity exposing the last persisted snapshot for a Bosch camera.

    On each successful background refresh the camera entity calls
    `async_notify_refreshed()` which bumps `image_last_updated` and writes
    a new access token. The frontend receives the state-change over WebSocket,
    uses the updated signed URL (/api/image_proxy/<entity_id>?token=<new>),
    and WKWebView treats it as a distinct resource — bypassing its heuristic
    disk cache.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "last_snapshot"
    _attr_content_type = "image/jpeg"
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: BoschCameraCoordinator,
        cam_id: str,
        entry: ConfigEntry,
    ) -> None:
        # ImageEntity.__init__ wires up hass, access_tokens, and calls async_update_token
        ImageEntity.__init__(self, hass)
        self._coordinator = coordinator
        self._cam_id = cam_id
        self._entry = entry

        info = coordinator.data.get(cam_id, {}).get("info", {})
        title = info.get("title", cam_id)
        hw = info.get("hardwareVersion", "CAMERA")

        self._display_name = f"Bosch {title}"
        self._model_name = get_display_name(hw)
        self._fw = info.get("firmwareVersion", "")
        self._mac = info.get("macAddress", "")

        self._attr_unique_id = f"{cam_id}_last_snapshot"

        # In-RAM copy of the last-served JPEG. async_notify_refreshed()
        # invalidates it on every persisted snapshot, so it stays fresh while
        # turning the per-request disk read into a per-refresh one (perf
        # 2026-06-18 — every dashboard client and the iOS app re-fetch the
        # same signed URL repeatedly between refreshes).
        self._cached_bytes: bytes | None = None

        # Register ourselves with the coordinator's camera entity so
        # BoschCamera can call async_notify_refreshed() after persisting.
        coordinator._image_entities[cam_id] = self

    async def async_will_remove_from_hass(self) -> None:
        """Unregister from coordinator on removal."""
        self._coordinator._image_entities.pop(self._cam_id, None)
        await super().async_will_remove_from_hass()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._cam_id)},
            name=self._display_name,
            manufacturer="Bosch",
            model=self._model_name,
            sw_version=self._fw,
            connections={("mac", self._mac)} if self._mac else set(),
        )

    async def async_image(self) -> bytes | None:
        """Return the latest persisted JPEG, falling back to camera RAM cache.

        Primary source: disk store (.storage/bosch_shc_camera/snapshots/).
        Fallback: camera entity's _cached_image (RAM only, lost on restart).
        Returns None only when both sources are empty (very first startup
        before any snapshot has been fetched).
        """
        # Serve the in-RAM copy if we already loaded it since the last
        # refresh — avoids a disk read on every /api/image_proxy request.
        # async_notify_refreshed() clears it when a new snapshot is persisted.
        if self._cached_bytes is not None:
            return self._cached_bytes
        disk_bytes = await load_snapshot(self.hass, self._cam_id)
        if disk_bytes:
            self._cached_bytes = disk_bytes
            return disk_bytes
        # Fallback to RAM cache from the camera entity. Do NOT store it as our
        # own cache: it's a transient cold-start fallback that the next disk
        # write supersedes, and caching it would shadow the disk snapshot.
        cam = self._coordinator._camera_entities.get(self._cam_id)
        if cam is not None:
            cached = cam._cached_image
            # Don't serve the 1×1 placeholder as a real snapshot image.
            if cached and len(cached) > 200:
                return cached  # type: ignore[no-any-return]  # value is correct at runtime; HA/external source is Any-typed
        return None

    async def async_notify_refreshed(self) -> None:
        """Called by BoschCamera after a fresh snapshot is persisted to disk.

        Bumps image_last_updated so HA pushes a state-change via WebSocket.
        The frontend's signed URL changes (new access token) — WKWebView
        cannot re-use its cached entry and must fetch fresh bytes.
        """
        # Invalidate the in-RAM copy: a new snapshot was just persisted, so
        # the next async_image() reloads the fresh bytes from disk exactly
        # once and serves that copy to all subsequent requests.
        self._cached_bytes = None
        self._attr_image_last_updated = dt_util.utcnow()
        self.async_update_token()
        self.async_write_ha_state()
        _LOGGER.debug(
            "bosch image entity %s: notified refresh at %s",
            self._cam_id,
            self._attr_image_last_updated,
        )

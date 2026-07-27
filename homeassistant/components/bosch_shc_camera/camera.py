"""Bosch Smart Home Camera — Camera Platform.

Each camera discovered via /v11/video_inputs becomes a HA camera entity.
Images are the latest motion-triggered event snapshots from the cloud API.

This is a still-image-only camera entity: it has no live streaming, no
stream_source, and no WebRTC/HLS support. Snapshots are fetched via the
cloud on-demand snap.jpg endpoint, a cached-Digest-creds LOCAL fallback
during a cloud outage, and the latest event snapshot as a last resort.
"""

import asyncio
from io import BytesIO
import logging
import math
import time
from typing import Any, override

import aiohttp
from bosch_shc_camera_client.auth_utils import async_digest_request
from PIL import Image

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BoschCameraCoordinator, _is_safe_bosch_url, get_options
from .cloud_ssl import async_get_bosch_cloud_session
from .const import (
    DOMAIN,
    JPEG_SIZE_FULL,
    TIMEOUT_SNAP,
    jpeg_size_for_width,
    with_jpeg_size,
)
from .models import (
    get_display_name,  # [S4] hoisted: avoid per-call import binding on hot path
)
from .snapshot_store import load_snapshot, save_snapshot
from .time_utils import parse_bosch_timestamp

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

IMAGE_REFRESH_INTERVAL = (
    1800  # fallback: seconds between background proactive refreshes
)
CLOUD_SNAP_CACHE_TTL = 30  # minimum seconds between cloud fetches (de-bounce)
DEFAULT_SNAPSHOT_INTERVAL = (
    1800  # default proactive background refresh interval (30 min)
)
IDLE_FRAME_INTERVAL = (
    60  # seconds — how often HA's camera proxy calls async_camera_image
)

# Worst-case cumulative time budget of the snapshot fallback cascade in
# _async_camera_image_impl, if every tier is attempted and every tier times
# out: cloud on-demand snap.jpg (10s), LOCAL outage snap.jpg via cached Digest
# creds (12s), latest-event snapshot (10s, capped from 20s — see call site).
# Logged at DEBUG for visibility into how long a single async_camera_image()
# call can bind the event loop before falling back to the cached
# image/placeholder.
SNAPSHOT_FALLBACK_MAX_BUDGET_SEC = 10 + 12 + 10

# Budget for the stale-cache refresh-and-fall-back-to-cached-image path in
# _async_camera_image_impl — must stay under HA core's own CAMERA_IMAGE_TIMEOUT
# (10s, homeassistant/components/camera/const.py) so a slow/failing REMOTE+LOCAL
# chain still leaves time to return the cached frame instead of the whole call
# being cancelled and serving nothing.
REFRESH_ON_STALE_CACHE_BUDGET_SEC = 8


def _fmt_event_ts(ts_str: str | None) -> str:
    """Format a Bosch event timestamp for a debug-log line.

    Never slice the raw string to 19 chars — that discards the offset
    (+02:00/Z) and recreates GitHub #34 (a truncated-then-relabelled-UTC
    timestamp read as +2h/CEST off). Uses the same documented parser as
    `extra_state_attributes`.
    """
    dt = parse_bosch_timestamp(ts_str)
    return dt.isoformat() if dt else ""


def _rotate_jpeg_180(jpeg_bytes: bytes) -> bytes:
    """Rotate a JPEG image by 180° using PIL. Sync — call via executor.

    Used by async_camera_image when the user enabled the Bild 180° drehen
    switch (ceiling-mounted indoor cameras). Typical 1280x720 JPEG: ~15-30 ms
    with libjpeg-turbo. Returns the original bytes if rotation fails.
    """
    try:
        img = Image.open(BytesIO(jpeg_bytes))
        rotated = img.rotate(180)
        out = BytesIO()
        rotated.save(out, format="JPEG", quality=90)
        return out.getvalue()
    except Exception as err:  # noqa: BLE001 — PIL can raise many undocumented decoder-specific errors; any failure must fall back to the original bytes, never break image serving
        _LOGGER.debug("rotate_jpeg_180 failed (%s) — returning original", err)
        return jpeg_bytes


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up camera entities — one per discovered Bosch camera."""
    opts = get_options(config_entry)
    if not opts.get("enable_snapshots", True):
        _LOGGER.debug("Camera snapshots disabled in options — skipping camera platform")
        return

    coordinator = config_entry.runtime_data
    entities = [
        BoschCamera(coordinator, cam_id, config_entry) for cam_id in coordinator.data
    ]
    async_add_entities(entities, update_before_add=False)


class BoschCamera(CoordinatorEntity[BoschCameraCoordinator], Camera):
    """Represents a single Bosch Smart Home camera in Home Assistant.

    • Shows the latest motion-triggered JPEG snapshot (refreshed every scan_interval)
    • Device groups with sensor and button entities on the same HA device
    • Still-image-only: no streaming support (no CameraEntityFeature.STREAM)
    • Image is refreshed on startup and every 30 minutes (snapshot_interval)
    """

    # 1x1 black JPEG — prevents HTTP 500 when no cached image available
    _PLACEHOLDER_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x08\x01\x01\x00\x00?\x00T\xdf\xb2\x80\x01\xff\xd9"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BoschCameraCoordinator,
        cam_id: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize a BoschCamera entity for one discovered camera."""
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)

        self._cam_id = cam_id
        self._entry = entry
        self.cached_image: bytes | None = self._PLACEHOLDER_JPEG
        self._force_image_refresh: bool = False  # bypasses HA image cache once
        # monotonic timestamp of last *successful* fetch (-inf = never fetched;
        # SENTINEL_RULE — CI VMs boot at ~200s monotonic so a finite
        # large-negative can read as "recent")
        self.last_image_fetch: float = -math.inf
        # monotonic timestamp of last *failed* fetch; separate so successes
        # always update the cache window
        self._last_failed_fetch: float = -math.inf
        self._refresh_inflight: bool = False  # synchronous guard: set before first yield, cleared in finally  # prevents concurrent async_trigger_image_refresh (replaces locked()+async-with race)
        # Tracks the most recently scheduled background image-refresh task
        # (startup delay or proactive coordinator-update trigger) so
        # async_will_remove_from_hass can cancel a still-pending one — without
        # this, unloading the entity mid-delay left a network task running
        # against an already-removed entity (bug-hunt 2026-07-27, Copilot review).
        self._image_refresh_task: asyncio.Task[None] | None = None

        info = coordinator.data.get(cam_id, {}).get("info", {})
        title = info.get("title", cam_id)

        self._display_name = f"Bosch {title}"
        self._attr_name = None  # entity is the main feature of the device; HA uses device name as friendly_name
        self._attr_unique_id = f"bosch_shc_cam_{cam_id.lower()}"
        self._model = info.get("hardwareVersion", "CAMERA")
        self.hw_version = info.get("hardwareVersion", "")
        self._model_name = get_display_name(self.hw_version)
        self._fw = info.get("firmwareVersion", "")
        self._mac = info.get("macAddress", "")

    # ── Startup ───────────────────────────────────────────────────────────────
    @override
    async def async_added_to_hass(self) -> None:
        """Called when entity is added to HA — kick off initial image fetch."""
        await super().async_added_to_hass()
        # Register with coordinator so button/service can trigger image refresh
        self.coordinator.camera_entities[self._cam_id] = self

        # Restore the last-persisted snapshot from disk so HA can serve a real
        # image immediately — before the first live fetch completes (~2-4 s).
        # This prevents the 1x1 black placeholder from flashing on a cold start.
        persisted = await load_snapshot(self.hass, self._cam_id)
        if persisted:
            self.cached_image = persisted
            # Back-date last_image_fetch so the normal snapshot_interval still
            # triggers a live refresh on schedule.  Using -math.inf would
            # trigger an immediate re-fetch; instead back-date by one full
            # snapshot_interval so the first refresh fires normally.
            # IMAGE_REFRESH_INTERVAL is the fixed cadence — never read
            # `entry.options["snapshot_interval"]` directly: the options-flow
            # field for it was removed (Bronze appropriate-polling requires a
            # fixed interval), but a HACS-migrated entry can still carry a
            # stale value under that same key, which a direct read would
            # silently keep honoring (bug-hunt 2026-07-27, Copilot review
            # round 3).
            self.last_image_fetch = time.monotonic() - IMAGE_REFRESH_INTERVAL
            _LOGGER.debug(
                "%s: restored %d-byte snapshot from disk",
                self._display_name,
                len(persisted),
            )

        # Fetch a real image shortly after startup (let coordinator settle first).
        self._image_refresh_task = self.hass.async_create_task(
            self.async_trigger_image_refresh(delay=2)
        )

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Called when entity is removed — unregister from coordinator + cancel any pending refresh."""
        self.coordinator.camera_entities.pop(self._cam_id, None)
        if self._image_refresh_task is not None and not self._image_refresh_task.done():
            self._image_refresh_task.cancel()
        await super().async_will_remove_from_hass()

    @override
    def _handle_coordinator_update(self) -> None:
        """Trigger a background proactive refresh on the configured interval."""
        now = time.monotonic()
        # Fixed cadence — see the async_added_to_hass comment above for why
        # this must not read entry.options["snapshot_interval"] directly.
        if now - self.last_image_fetch >= IMAGE_REFRESH_INTERVAL:
            self._image_refresh_task = self.hass.async_create_task(
                self.async_trigger_image_refresh(delay=0)
            )

        super()._handle_coordinator_update()

    async def async_trigger_image_refresh(self, delay: float = 0) -> None:
        """Fetch a fresh image and force HA's camera proxy to serve it.

        Primarily used on startup and on the proactive refresh interval. For
        CAMERA_360 (whose REMOTE snap.jpg returns 401) this runs the LOCAL Digest-auth fallback so
        the camera cache stays warm even though async_camera_image's cloud fetch
        would return None for it.

        Sets _force_image_refresh=True so that frame_interval returns 0.1 s,
        causing HA's image cache to expire on the very next proxy request.
        After the fetch, frame_interval reverts to its normal value.

        Concurrent calls are short-circuit via _refresh_inflight: the flag is set
        synchronously before the first ``await``, so a second caller sees it
        immediately and returns without opening a duplicate PUT /connection.
        This prevents startup + stream-stop + proactive-tick from each burning
        the Bosch 3-session budget and racing on cached_image /
        _force_image_refresh.

        Note: the previous implementation used ``_refresh_lock.locked()`` +
        ``async with _refresh_lock``. That left a yield-point gap between the
        check and the acquire (``__aenter__`` is a coroutine), allowing two
        delayed callers to both pass the check and proceed in sequence. The
        synchronous boolean flag closes that window entirely.
        """
        if delay:
            await asyncio.sleep(delay)

        # Skip refresh when privacy mode is ON — the camera blocks the view,
        # so any image we'd fetch would just be the stale last event snapshot.
        # The frontend card shows the "Privat-Modus aktiv" placeholder instead.
        shc = self.coordinator.shc_state_cache.get(self._cam_id, {})
        if shc.get("privacy_mode") is True:
            _LOGGER.debug(
                "%s: skipping image refresh — privacy mode is ON", self._display_name
            )
            return

        # Synchronous in-flight guard: set before any yield so a second caller
        # (even one that just woke from asyncio.sleep) sees the flag immediately.
        if self._refresh_inflight:
            _LOGGER.debug(
                "%s: refresh already in progress — skipping duplicate",
                self._display_name,
            )
            return

        self._refresh_inflight = True
        self._force_image_refresh = True
        try:
            # Fast path: populate cached_image from the latest event snapshot
            # immediately so the HA camera proxy can serve something while the
            # live snap is fetching. This ensures the card shows a real image
            # within ~1s of startup/stream-stop, instead of waiting 5-15s for
            # the PUT /connection + snap.jpg round-trip.
            # Guard: only seed when we hold nothing but the 1x1 black placeholder
            # (not self.cached_image checked `not bytes`, but placeholder is
            # truthy — use identity check).
            if self.cached_image is self._PLACEHOLDER_JPEG:
                # Call the event-snapshot fetcher directly rather than
                # async_camera_image() — that already runs the full live
                # REMOTE/LOCAL cascade, and the slow path below runs it
                # again immediately after, doubling the connection/snapshot
                # requests on every cold start (bug-hunt 2026-07-27,
                # Copilot review round 3).
                quick = await self.coordinator.async_fetch_fresh_event_snapshot(
                    self._cam_id
                )
                if quick and quick is not self._PLACEHOLDER_JPEG:
                    self.cached_image = quick
                    self.last_image_fetch = time.monotonic()
                    _LOGGER.debug(
                        "%s: quick event-snapshot seed — %d bytes",
                        self._display_name,
                        len(quick),
                    )
                    self.async_write_ha_state()

            # Slow path: fetch a fresh live snapshot via PUT /connection + snap.jpg
            image = await self.coordinator.async_fetch_live_snapshot(self._cam_id)
            # Fallback for cameras whose REMOTE snap.jpg returns 401 (e.g. CAMERA_360):
            # try LOCAL connection with Digest auth for a direct LAN snapshot.
            if not image:
                image = await self.coordinator.async_fetch_live_snapshot_local(
                    self._cam_id
                )

            # Last resort: seed from the latest event snapshot ONLY on a true cold
            # start (nothing cached yet). NEVER fall back to it when we already
            # hold a frame — the "latest event" can be days old (last_event frozen
            # when no new motion / FCM stale), so replacing a working live frame
            # with it flipped the card from the current snapshot back to an ancient
            # event picture after a transient live-fetch failure on the proactive
            # refresh tick (privacy OFF).
            # The placeholder (1x1 black) does NOT count as a real frame — on a
            # genuine cold start we still want to seed from the event image.
            _has_real_frame = (
                bool(self.cached_image)
                and self.cached_image is not self._PLACEHOLDER_JPEG
            )
            if not image and not _has_real_frame:
                image = await self.coordinator.async_fetch_fresh_event_snapshot(
                    self._cam_id
                )

            if image:
                # Privacy TOCTOU guard: re-read privacy from the live cache
                # immediately before writing cached_image. The coordinator may
                # have updated between the top-of-method check and now (privacy
                # turned ON during the 2-10 s fetch). Writing a just-fetched
                # live frame while privacy is transitioning ON would serve a
                # real-scene image until the next refresh.
                shc_state = self.coordinator.shc_state_cache.get(self._cam_id, {})
                if shc_state.get("privacy_mode") is True:
                    _LOGGER.debug(
                        "%s: privacy turned ON during fetch — discarding frame",
                        self._display_name,
                    )
                    return
                self.cached_image = image
                self.last_image_fetch = time.monotonic()
                _LOGGER.debug(
                    "%s: background refresh — %d bytes",
                    self._display_name,
                    len(image),
                )
                self.async_write_ha_state()

                # Persist to disk (defence-in-depth: privacy gate above
                # already prevents reaching here when privacy is ON)
                if not shc_state.get("privacy_mode"):
                    await save_snapshot(self.hass, self._cam_id, image)
                    img_entity = self.coordinator.image_entities.get(self._cam_id)
                    if img_entity is not None:
                        await img_entity.async_notify_refreshed()
            elif _has_real_frame:
                # Live fetch was unavailable (transient 444 quota / network blip)
                # but we already hold a good frame — keep it instead of flipping to
                # a stale event image, and back off a full interval rather than
                # retrying every coordinator tick.
                self.last_image_fetch = time.monotonic()
                _LOGGER.debug(
                    "%s: live refresh unavailable — keeping last good frame",
                    self._display_name,
                )

        except Exception as err:  # noqa: BLE001 — best-effort background refresh spanning multiple fetch tiers + disk I/O; any failure must be swallowed so the next coordinator tick retries, never crash the entity
            _LOGGER.debug("%s: image refresh failed: %s", self._display_name, err)
        finally:
            self._refresh_inflight = False
            self._force_image_refresh = False

    # ── Helpers ───────────────────────────────────────────────────────────────
    @property
    def _cam_data(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._cam_id, {})  # type: ignore[no-any-return]

    @property
    @override
    def motion_detection_enabled(self) -> bool:
        """Whether motion detection is currently enabled on this camera.

        Reads from the same cloud API data as the Motion Detection switch.
        Enables the standard HA camera.enable/disable_motion_detection services.
        """
        settings = self.coordinator.motion_settings(self._cam_id)
        if not settings:
            return False
        return bool(settings.get("enabled", False))

    @override
    async def async_enable_motion_detection(self, **kwargs: Any) -> None:
        """Enable motion detection via standard HA camera service."""
        settings = self.coordinator.motion_settings(self._cam_id)
        sensitivity = (
            settings.get("motionAlarmConfiguration", "HIGH") if settings else "HIGH"
        )
        success = await self.coordinator.async_put_camera(
            self._cam_id,
            "motion",
            {"enabled": True, "motionAlarmConfiguration": sensitivity},
        )
        if not success:
            raise HomeAssistantError(
                f"{self._display_name}: failed to enable motion detection"
            )
        # Optimistic cache update + write-lock timestamp — motion is only
        # ever re-fetched by the ~5-min slow tier, so without this,
        # motion_detection_enabled would read stale data for minutes after
        # this service call succeeded (bug-hunt 2026-07-27, Copilot review
        # round 3).
        self.coordinator.data.setdefault(self._cam_id, {}).setdefault(
            "motion", {}
        ).update({"enabled": True, "motionAlarmConfiguration": sensitivity})
        self.coordinator.motion_set_at[self._cam_id] = time.monotonic()
        self.hass.async_create_task(self.coordinator.async_request_refresh())

    @override
    async def async_disable_motion_detection(self, **kwargs: Any) -> None:
        """Disable motion detection via standard HA camera service."""
        settings = self.coordinator.motion_settings(self._cam_id)
        sensitivity = (
            settings.get("motionAlarmConfiguration", "HIGH") if settings else "HIGH"
        )
        success = await self.coordinator.async_put_camera(
            self._cam_id,
            "motion",
            {"enabled": False, "motionAlarmConfiguration": sensitivity},
        )
        if not success:
            raise HomeAssistantError(
                f"{self._display_name}: failed to disable motion detection"
            )
        # See async_enable_motion_detection above.
        self.coordinator.data.setdefault(self._cam_id, {}).setdefault(
            "motion", {}
        ).update({"enabled": False, "motionAlarmConfiguration": sensitivity})
        self.coordinator.motion_set_at[self._cam_id] = time.monotonic()
        self.hass.async_create_task(self.coordinator.async_request_refresh())

    @property
    @override
    def frame_interval(self) -> float:
        """How often (seconds) HA requests a fresh image from this camera.

        When _force_image_refresh is set: 0.1 s — forces immediate cache expiry
        so HA's next proxy request fetches the new snapshot right away.
        Otherwise:      IDLE_FRAME_INTERVAL (60 s) — HA calls async_camera_image
                        every 60 s. The actual cloud fetch rate is governed by
                        CLOUD_SNAP_CACHE_TTL (30 s) inside async_camera_image:
                        stale cache → return cached immediately + bg refresh.
                        snapshot_interval (default 1800 s) controls the proactive
                        background refresh in _handle_coordinator_update, not this.
        """
        if self._force_image_refresh:
            return 0.1
        return float(IDLE_FRAME_INTERVAL)

    @property
    def _token(self) -> str:
        return self._entry.data.get("bearer_token", "")  # type: ignore[no-any-return]

    # ── HA metadata ───────────────────────────────────────────────────────────
    @property
    @override
    def brand(self) -> str:
        """Return the device brand."""
        return "Bosch"

    @property
    @override
    def model(self) -> str:
        """Return the raw hardwareVersion model string."""
        return self._model  # type: ignore[no-any-return]

    _UNAVAILABLE_STATUSES = ("OFFLINE", "UPDATING", "SESSION_LIMIT")

    @property
    @override
    def available(self) -> bool:
        """Return False while this camera is offline/updating/session-limited, or the coordinator is down."""
        # Firmware install reboots the camera (3-7 min). Mark unavailable so
        # automations and the UI don't poll a dead endpoint or surface stale
        # snapshots as live state.
        is_updating = getattr(self.coordinator, "is_updating", None)
        if is_updating is not None and is_updating(self._cam_id):
            return False
        if not self.coordinator.last_update_success:
            return False
        # A successful account-level coordinator update does not mean every
        # camera is reachable — check this camera's own cached status too,
        # otherwise an OFFLINE/UPDATING/SESSION_LIMIT camera stays marked
        # available and serves stale imagery as if it were live.
        return self._cam_data.get("status", "UNKNOWN") not in self._UNAVAILABLE_STATUSES

    @property
    @override
    def device_info(self) -> DeviceInfo:
        """Return device registry info for this camera."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._cam_id)},
            name=self._display_name,
            manufacturer="Bosch",
            model=self._model_name,
            sw_version=self._fw,
            connections={("mac", self._mac)} if self._mac else set(),
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional camera state attributes."""
        cam_data = self._cam_data
        events = cam_data.get("events", [])
        latest = events[0] if events else {}

        info = cam_data.get("info", {})
        # Never slice a Bosch timestamp to 19 chars — it discards the offset
        # (+02:00/Z), recreating GitHub #34 (last_event showed +2h/CEST
        # because the naive wall-clock reading got re-labelled as UTC).
        # parse_bosch_timestamp() is the documented, correct parser.
        last_event_dt = parse_bosch_timestamp(latest.get("timestamp"))
        return {
            "camera_id": self._cam_id,
            "status": cam_data.get("status", "UNKNOWN"),
            "last_event": last_event_dt.isoformat() if last_event_dt else "",
            "event_type": latest.get("eventType", ""),
            "model_name": self._model_name,
            "hardware_version": self.hw_version,
            "firmware": self._fw,
            "mac": self._mac,
            # Bosch-app camera order. Mirrors the float priority returned by
            # GET /v11/video_inputs (settable via PUT /v11/video_inputs/order).
            "bosch_priority": info.get("priority"),
        }

    # ── Snapshot image ────────────────────────────────────────────────────────
    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Public entrypoint — wraps the implementation so any uncaught exception still returns a valid image.

        Returns a valid (placeholder) JPEG instead of letting HA's camera
        proxy serve a textual `500: Internal Server Error` body (26 bytes of
        plain text in place of an image).

        An unhandled exception in `_async_camera_image_impl` would otherwise
        propagate up and HA would return a bare 500. Lovelace's `<img>`
        element renders the literal text bytes as a brown error frame, so we
        always serve a real (placeholder, if nothing else) JPEG instead.
        """
        try:
            result = await self._async_camera_image_impl(width, height)
            jpeg = result or self._PLACEHOLDER_JPEG
        except asyncio.CancelledError:
            raise  # let cancellation propagate cleanly
        except Exception as err:  # noqa: BLE001 — explicit safety net documented above: any uncaught exception here must still yield a valid JPEG instead of HA's camera proxy serving a raw 500 body
            _LOGGER.debug(
                "%s: async_camera_image failed (%s) — serving placeholder",
                self._display_name,
                err,
            )
            jpeg = self.cached_image or self._PLACEHOLDER_JPEG
        # Apply 180° rotation if the user enabled it via the Bild 180° drehen
        # switch (ceiling-mounted indoor cameras). Skip the placeholder JPEG.
        # [S5] Use None default instead of {} to avoid allocating a throwaway dict
        # on every call when the attribute exists (production path always has it).
        _rot_cache = getattr(self.coordinator, "image_rotation_180", None)
        rotate = bool(_rot_cache and _rot_cache.get(self._cam_id))
        if rotate and jpeg is not self._PLACEHOLDER_JPEG and jpeg:
            jpeg = await self.hass.async_add_executor_job(_rotate_jpeg_180, jpeg)
        return jpeg

    async def _async_camera_image_impl(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the best available JPEG snapshot, tried in order.

        1. Cloud proxy on-demand  — PUT /connection REMOTE + snap.jpg.
           If no cached image: fetches fresh synchronously (~3 s).
           If cached image is older than CLOUD_SNAP_CACHE_TTL (30 s): fetches
           fresh synchronously so the user always sees a current image.
        2. LOCAL snap.jpg with cached Digest creds (cloud-outage fallback).
        3. Cached image           — fallback when cloud fetch fails (e.g. CAMERA_360
           whose REMOTE snap.jpg returns 401; refreshed via async_trigger_image_refresh
           using LOCAL connection).
        4. Latest event snapshot  — last resort on very first startup before any
           cloud fetch has completed.

        The card calls trigger_snapshot on page load / tab switch / 60s timer,
        which sets _force_image_refresh=True (frame_interval → 0.1s) and fetches
        a fresh image via async_trigger_image_refresh. This ensures HA's camera
        proxy serves the fresh image on the next request instead of its 60s cache.

        width/height: passed by HA when the card requests ?width=N.
        """
        # Privacy mode ON: both coordinator fetch methods below already
        # short-circuit to None (the camera returns 0-byte snap.jpg while
        # privacy is engaged), but without this early return the cascade
        # falls through tiers 2-3 to `self.cached_image` — the last REAL
        # scene from before privacy was enabled — and keeps serving it
        # through the camera proxy indefinitely. Return None here so the
        # public wrapper's `result or _PLACEHOLDER_JPEG` serves the
        # placeholder instead (bug-hunt 2026-07-27, Copilot review).
        if self.coordinator.shc_state_cache.get(self._cam_id, {}).get("privacy_mode"):
            return None

        # Verifying Bosch-cloud session: REMOTE proxy snap.jpg fetches below are
        # TLS-validated against the pinned Bosch CA. The LOCAL Digest paths pass
        # ssl=False per request (camera LAN IP, self-signed) which overrides this
        # session's connector for those calls only.
        session = await async_get_bosch_cloud_session(self.hass)
        token = self._token
        headers_bearer = {"Authorization": f"Bearer {token}", "Accept": "*/*"}
        # snap.jpg resolution for this request: JPEG_SIZE_THUMB/_MEDIUM for a
        # card-sized request, None (= keep full resolution) otherwise. Only the
        # snapshot fetches on this request path get it — the background refresh
        # and the image.* entity call the coordinator without a width and so
        # keep JPEG_SIZE_FULL for the persisted snapshot.
        req_jpeg_size = jpeg_size_for_width(width)
        _LOGGER.debug(
            "%s: snapshot fallback chain start (worst-case budget %ds)",
            self._display_name,
            SNAPSHOT_FALLBACK_MAX_BUDGET_SEC,
        )

        # ── 1. Cloud proxy on-demand snapshot (PUT /connection REMOTE → snap.jpg) ──
        # Primary snapshot method for idle cameras. Two modes:
        #
        # a) No cached image yet (first load / cache empty): fetch synchronously so
        #    HA has something to serve immediately. ~3s on cold cache.
        #
        # b) Cached image exists but is stale (> CLOUD_SNAP_CACHE_TTL): fetch fresh
        #    synchronously so the user always sees a current image. The card triggers
        #    this via trigger_snapshot service which sets _force_image_refresh, so
        #    HA's frame_interval cache is bypassed and the fresh image is served.
        now = time.monotonic()
        cache_stale = (now - self.last_image_fetch) >= CLOUD_SNAP_CACHE_TTL
        if (
            not self.cached_image or self.cached_image is self._PLACEHOLDER_JPEG
        ) and cache_stale:
            # First load — must wait synchronously. The placeholder is a real
            # (truthy) 1x1 black JPEG, so `not self.cached_image` alone never
            # fires while we still hold it — use the identity check too (mirror
            # of async_trigger_image_refresh). Without this, a cold-boot proxy
            # request (HA Companion app on restart, before the async disk-restore
            # in async_added_to_hass completes) was served the black placeholder
            # instead of fetching a real frame → "black image on mobile".
            # The `and cache_stale` gate is the backoff: a persistently-offline
            # camera (every fetch fails, placeholder stays) would otherwise
            # re-enter this slow REMOTE+LOCAL chain on EVERY proxy request,
            # since the placeholder identity is true regardless of staleness.
            # On true first load last_image_fetch is the boot sentinel, so
            # cache_stale is True and this still fetches immediately.
            fresh: bytes | None = await self.coordinator.async_fetch_live_snapshot(
                self._cam_id, jpeg_size=req_jpeg_size
            )
            if not fresh:
                # REMOTE snap.jpg returns 401 on CAMERA_360 — try LOCAL Digest fallback
                fresh = await self.coordinator.async_fetch_live_snapshot_local(
                    self._cam_id, jpeg_size=req_jpeg_size
                )
            if fresh:
                # Only a full-resolution fetch may update the shared cache —
                # otherwise a width=N (thumbnail) request would poison
                # cached_image/last_image_fetch, and a subsequent full-res
                # request within CLOUD_SNAP_CACHE_TTL would be served that
                # undersized thumbnail instead of fetching fresh
                # (bug-hunt 2026-07-27, Copilot review).
                if req_jpeg_size is None:
                    self.cached_image = fresh
                    self.last_image_fetch = now
                _LOGGER.debug(
                    "%s: cloud proxy snapshot %d bytes (first load)",
                    self._display_name,
                    len(fresh),
                )
                return fresh
            # Fetch failed while holding only the placeholder (camera offline /
            # cloud blip). Stamp now so cache_stale goes False and we back off —
            # don't re-run the slow REMOTE+LOCAL chain on every proxy request;
            # retry after CLOUD_SNAP_CACHE_TTL. Mirrors the stale branch below.
            # Falls through to 2 / cached / event-snapshot fallback.
            self.last_image_fetch = now
        elif cache_stale:
            cache_age = now - self.last_image_fetch
            # Always fetch fresh synchronously when cache is stale.
            # The old background-refresh approach returned the stale image
            # and refreshed async — but HA's frame_interval meant the fresh
            # image was never served until the NEXT cycle, so the user saw
            # the same stale frame repeatedly.
            _LOGGER.debug(
                "%s: cache stale (%ds) — fetching fresh synchronously",
                self._display_name,
                int(cache_age),
            )
            # Bounded well under HA's own CAMERA_IMAGE_TIMEOUT (10s, see
            # homeassistant/components/camera/const.py) — we already hold a
            # real cached image here, so on a slow/outage REMOTE+LOCAL chain
            # we must fall back to it before HA's outer timeout cancels this
            # call entirely and serves nothing (the worst-case REMOTE+LOCAL
            # chain alone can run well past 10s).
            fresh2: bytes | None = None
            try:
                async with asyncio.timeout(REFRESH_ON_STALE_CACHE_BUDGET_SEC):
                    fresh2 = await self.coordinator.async_fetch_live_snapshot(
                        self._cam_id, jpeg_size=req_jpeg_size
                    )
                    if not fresh2:
                        # REMOTE snap.jpg returns 401 on CAMERA_360 — try LOCAL Digest fallback
                        fresh2 = await self.coordinator.async_fetch_live_snapshot_local(
                            self._cam_id, jpeg_size=req_jpeg_size
                        )
            except TimeoutError:
                _LOGGER.debug(
                    "%s: fresh fetch exceeded %ds budget — returning cached (%ds old)",
                    self._display_name,
                    REFRESH_ON_STALE_CACHE_BUDGET_SEC,
                    int(cache_age),
                )
                return self.cached_image
            if fresh2:
                # See the tier-1a comment above: only a full-resolution fetch
                # may update the shared cache.
                if req_jpeg_size is None:
                    self.cached_image = fresh2
                    self.last_image_fetch = now
                return fresh2
            # Both REMOTE + LOCAL failed — advance timestamp so next tick retries instead of looping
            self.last_image_fetch = now
            _LOGGER.debug(
                "%s: fresh fetch failed — returning cached (%ds old)",
                self._display_name,
                int(cache_age),
            )
            return self.cached_image
        else:
            return self.cached_image

        # ── 2. LOCAL snap.jpg with cached Digest creds (cloud-outage fallback) ──
        # When the Bosch cloud or auth server is unreachable, PUT /connection
        # REMOTE fails — but we may still have valid LOCAL creds from the
        # previous session (cached in coordinator.local_creds_cache). Try
        # fetching snap.jpg directly from the camera's LAN IP using those
        # creds before giving up. Digest creds are ephemeral (camera rotates
        # them on reboot) but usually stable for minutes to hours.
        creds = self.coordinator.local_creds_cache.get(self._cam_id)
        if creds and self.coordinator.auth_outage_count > 0:
            local_user = creds.get("user", "")
            local_pass = creds.get("password", "")
            host = creds.get("host", "")
            port = creds.get("port", 443)
            if local_user and local_pass and host:
                snap_url = with_jpeg_size(
                    f"https://{host}:{port}/snap.jpg?JpegSize={JPEG_SIZE_FULL}",
                    req_jpeg_size,
                )
                outage_data: bytes | None = None
                try:
                    async with asyncio.timeout(12):
                        async with await async_digest_request(
                            session,
                            "GET",
                            snap_url,
                            local_user,
                            local_pass,
                            timeout=TIMEOUT_SNAP,
                            ssl=False,
                        ) as resp:
                            if resp.status == 200 and "image" in resp.headers.get(
                                "Content-Type", ""
                            ):
                                outage_data = await resp.read()
                except (TimeoutError, aiohttp.ClientError) as err:
                    _LOGGER.debug("LOCAL outage snap failed: %s", err)
                    outage_data = None
                if outage_data:
                    self.cached_image = outage_data
                    self.last_image_fetch = time.monotonic()
                    _LOGGER.info(
                        "%s: outage fallback — LOCAL snap.jpg %d bytes via cached Digest creds",
                        self._display_name,
                        len(outage_data),
                    )
                    return self.cached_image

        # ── 3. Cached image (fallback for cameras whose REMOTE snap.jpg needs auth) ──
        # For cameras like CAMERA_360 the cloud fetch above returns None;
        # async_trigger_image_refresh keeps this cache warm via LOCAL connection.
        # The placeholder is a real (truthy) 1x1 black JPEG, so `if
        # self.cached_image:` alone would intercept it here too, before tier 4
        # (the actual last resort) ever runs on a genuine cold start — use the
        # identity check too, mirroring the tier-2 guard above.
        if self.cached_image and self.cached_image is not self._PLACEHOLDER_JPEG:
            return self.cached_image

        # ── 4. Latest event snapshot (last resort — first startup before cloud fetch runs) ──
        events = self._cam_data.get("events", [])
        for ev in events:
            img_url = ev.get("imageUrl")
            if not img_url:
                continue
            if not _is_safe_bosch_url(img_url):
                _LOGGER.warning("Unsafe imageUrl rejected: %s", img_url[:60])
                continue
            try:
                # Capped from 20s to 10s: this is the last tier of the
                # snapshot fallback cascade (10/12/10s) — a 20s budget
                # here alone exceeded HA's CameraImageView outer timeout
                # (CAMERA_IMAGE_TIMEOUT, 10s), so an already-cancelled
                # request could still bind up to 20s of event-loop time on a
                # discarded fetch. 10s matches the other proxy-fetch tiers.
                async with asyncio.timeout(10):
                    async with session.get(img_url, headers=headers_bearer) as resp:
                        if resp.status == 200:
                            self.cached_image = await resp.read()
                            self.last_image_fetch = time.monotonic()
                            _LOGGER.debug(
                                "%s: event snapshot %d bytes @ %s",
                                self._display_name,
                                len(self.cached_image),
                                _fmt_event_ts(ev.get("timestamp")),
                            )
                            return self.cached_image
                        if resp.status == 401:
                            _LOGGER.warning(
                                "%s: token expired — update via integration options",
                                self._display_name,
                            )
                            return self.cached_image
                        # e.g. 403/404/410 = expired URL — try next event
                        _LOGGER.debug(
                            "%s: event snapshot HTTP %d @ %s — trying next",
                            self._display_name,
                            resp.status,
                            _fmt_event_ts(ev.get("timestamp")),
                        )
            except (TimeoutError, aiohttp.ClientError) as err:
                _LOGGER.debug("%s: event snapshot error: %s", self._display_name, err)

        # Return last cached image if all methods failed
        return self.cached_image or self._PLACEHOLDER_JPEG

"""Bosch Smart Home Camera — Camera Platform.

Each camera discovered via /v11/video_inputs becomes a HA camera entity.
Images are the latest motion-triggered event snapshots from the cloud API.

If a live proxy connection has been opened (via the "Open Live Stream" button
or the bosch_shc_camera.open_live_connection service), the entity exposes
a stream_source (rtsps:// URL on port 443) for full 30fps H.264 + AAC audio.

Stream URL format:
  rtsps://proxy-NN.live.cbs.boschsecurity.com:443/{hash}/rtsp_tunnel
    ?inst=2&enableaudio=1&fmtp=1&maxSessionDuration=3600

Note: HA's stream component must support rtsps:// (RTSP over TLS).
The stream requires -tls_verify 0 / insecure TLS (Bosch private CA).
If HA cannot open rtsps://, use ffplay from the Python CLI tool instead.

Stream session limit: Bosch enforces maxSessionDuration=3600 (60 minutes).
After 60 minutes the stream stops and must be restarted manually.
"""

import asyncio
import logging
import time
from typing import Any, override

import aiohttp
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from bosch_shc_camera_client.auth_utils import async_digest_request

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
    WebRTCSendMessage,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import (
    BoschCameraConfigEntry,
    BoschCameraCoordinator,
    _is_safe_bosch_url,
    get_options,
)
from .cloud_ssl import async_get_bosch_cloud_session
from .const import (
    AUTO_PLAY_DEFAULT_VALUES,
    DOMAIN,
    LIVE_SESSION_TTL,
    STREAM_START_SKIPPED,
    TIMEOUT_SNAP,
)
from .mjpeg_snapshot import fetch_mjpeg_snapshot
from .models import (
    get_display_name,
    get_model_config,
)  # [S4] hoisted: avoid per-call import binding on hot path
from .snapshot_store import load_snapshot, save_snapshot
from .switch import _redact_rtsp_creds

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

# Worst-case cumulative time budget of the 5-tier snapshot fallback cascade in
# _async_camera_image_impl, if every tier is attempted and every tier times
# out: tier1 LOCAL live-proxy snap (6s) OR REMOTE live-proxy snap + one renew
# retry (10s + 10s), tier2b LOCAL outage snap.jpg (12s), tier4 latest-event
# snapshot (10s, capped from 20s — see call site). Logged at DEBUG for
# visibility into how long a single async_camera_image() call can bind the
# event loop before falling back to the cached image/placeholder.
SNAPSHOT_FALLBACK_MAX_BUDGET_SEC = 10 + 10 + 12 + 10


def _rotate_jpeg_180(jpeg_bytes: bytes) -> bytes:
    """Rotate a JPEG image by 180° using PIL. Sync — call via executor.

    Used by async_camera_image when the user enabled the Bild 180° drehen
    switch (ceiling-mounted indoor cameras). Typical 1280×720 JPEG: ~15-30 ms
    with libjpeg-turbo. Returns the original bytes if rotation fails.
    """
    try:
        from io import BytesIO

        from PIL import Image

        img = Image.open(BytesIO(jpeg_bytes))
        rotated = img.rotate(180)
        out = BytesIO()
        rotated.save(out, format="JPEG", quality=90)
        return out.getvalue()
    except (OSError, ValueError) as err:
        _LOGGER.debug("rotate_jpeg_180 failed (%s) — returning original", err)
        return jpeg_bytes


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
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
    • Exposes stream_source (RTSP) once a live connection has been established
    • Device groups with sensor and button entities on the same HA device
    • Camera state is "streaming" when live proxy is active, "idle" otherwise
    • Image is refreshed on startup, on stream stop, and every 30 minutes
    """

    # 1×1 black JPEG — prevents HTTP 500 when no cached image available
    _PLACEHOLDER_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x08\x01\x01\x00\x00?\x00T\xdf\xb2\x80\x01\xff\xd9"
    _attr_has_entity_name = True
    # The (redacted) stream/proxy URLs rotate on every reconnect, so recording
    # them churns the `state_attributes` table with no history value (HA#39).
    # Keep them visible live; never historize them.
    _unrecorded_attributes = frozenset({"live_rtsps", "live_proxy", "stream_url"})

    def __init__(
        self,
        coordinator: BoschCameraCoordinator,
        cam_id: str,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the Bosch camera entity."""
        CoordinatorEntity.__init__(self, coordinator)
        Camera.__init__(self)
        # HA core's Camera.__init__ sets _supports_native_async_webrtc=True purely
        # because this class overrides async_handle_async_webrtc_offer() (for the
        # pre-warm wait below) — regardless of what that override actually does.
        # That flag then makes async_refresh_providers() skip go2rtc provider
        # detection entirely (_webrtc_provider stays None forever) while
        # camera_capabilities unconditionally advertises WEB_RTC support anyway,
        # so every real offer hits super()'s `if self._webrtc_provider` check,
        # finds None, and raises "Camera does not support WebRTC" (issue #40).
        # Force it back off so core's normal go2rtc provider bookkeeping runs;
        # our override still executes on every offer via normal polymorphism —
        # the flag only gates capability/provider bookkeeping, not dispatch.
        self._supports_native_async_webrtc = False
        # stream_options is set dynamically in stream_source() based on connection
        # type (LOCAL needs rtsp_transport=tcp; REMOTE uses FFmpeg default).

        self._cam_id = cam_id
        self._entry = entry
        self.cached_image: bytes | None = self._PLACEHOLDER_JPEG
        self._force_image_refresh: bool = False  # bypasses HA image cache once
        self.last_image_fetch: float = float(
            "-inf"
        )  # monotonic timestamp of last *successful* fetch (-inf = never fetched; SENTINEL_RULE — CI VMs boot at ~200s monotonic so a finite large-negative can read as "recent")
        self._last_failed_fetch: float = float(
            "-inf"
        )  # monotonic timestamp of last *failed* fetch; separate so successes always update the cache window
        self._refresh_inflight: bool = False  # synchronous guard: set before first yield, cleared in finally  # prevents concurrent _async_trigger_image_refresh (replaces locked()+async-with race)
        self._was_streaming: bool = False

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
        # image immediately — before the first live fetch completes (~2–4 s).
        # This prevents the 1×1 black placeholder from flashing on a cold start.
        persisted = await load_snapshot(self.hass, self._cam_id)
        if persisted:
            self.cached_image = persisted
            # Back-date _last_image_fetch so the normal snapshot_interval still
            # triggers a live refresh on schedule.  Using float('-inf') would
            # trigger an immediate re-fetch; instead back-date by one full
            # snapshot_interval so the first refresh fires normally.
            # [S7] IMAGE_REFRESH_INTERVAL == DEFAULT_OPTIONS["snapshot_interval"] == 1800;
            # direct read avoids inline import + full dict copy (once-per-restart path)
            snap_interval = float(
                int(
                    self._entry.options.get("snapshot_interval", IMAGE_REFRESH_INTERVAL)
                )
            )
            self.last_image_fetch = time.monotonic() - snap_interval
            _LOGGER.debug(
                "%s: restored %d-byte snapshot from disk",
                self._display_name,
                len(persisted),
            )

        # Fetch a real image shortly after startup (let coordinator settle first).
        self.hass.async_create_task(self.async_trigger_image_refresh(delay=2))

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Called when entity is removed — unregister from coordinator."""
        self.coordinator.camera_entities.pop(self._cam_id, None)
        await super().async_will_remove_from_hass()

    @override
    def _handle_coordinator_update(self) -> None:
        """Detect streaming → idle transitions and trigger background 30-min refresh."""
        is_now_streaming = self.is_streaming

        # Stream just stopped → grab a fresh event snapshot immediately
        if self._was_streaming and not is_now_streaming:
            self.hass.async_create_task(self.async_trigger_image_refresh(delay=2))

        # Proactive background refresh (even when nobody has the page open).
        # Interval: snapshot_interval option (default 1800 s / 30 min).
        elif not is_now_streaming:
            now = time.monotonic()
            # [S3] Read single key directly — avoids full dict(DEFAULT_OPTIONS)+update() copy
            proactive_interval = float(
                int(
                    self._entry.options.get("snapshot_interval", IMAGE_REFRESH_INTERVAL)
                )
            )
            if now - self.last_image_fetch >= proactive_interval:
                self.hass.async_create_task(self.async_trigger_image_refresh(delay=0))

        self._was_streaming = is_now_streaming
        super()._handle_coordinator_update()

    async def async_trigger_image_refresh(self, delay: float = 0) -> None:
        """Fetch a fresh image and force HA's camera proxy to serve it.

        Primarily used on startup and after stream stop. For CAMERA_360 (whose
        REMOTE snap.jpg returns 401) this runs the LOCAL Digest-auth fallback so
        the camera cache stays warm even though async_camera_image's cloud fetch
        would return None for it.

        Sets _force_image_refresh=True so that frame_interval returns 0.1 s,
        causing HA's image cache to expire on the very next proxy request.
        After the fetch, frame_interval reverts to its normal value.

        Concurrent calls are short-circuit via _refresh_inflight: the flag is set
        synchronously before the first ``await``, so a second caller sees it
        immediately and returns without opening a duplicate PUT /connection.
        This prevents startup + stream-stop + proactive-tick from each burning
        the Bosch 3-session budget and racing on _cached_image /
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
            # Fast path: populate _cached_image from the latest event snapshot
            # immediately so the HA camera proxy can serve something while the
            # live snap is fetching. This ensures the card shows a real image
            # within ~1s of startup/stream-stop, instead of waiting 5-15s for
            # the PUT /connection + snap.jpg round-trip.
            # Guard: only seed when we hold nothing but the 1×1 black placeholder
            # (not self.cached_image checked `not bytes`, but placeholder is
            # truthy — use identity check).
            if self.cached_image is self._PLACEHOLDER_JPEG:
                quick = await self.async_camera_image()
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
            # Skip when streaming — opening a new PUT /connection kills the active RTSP session
            image = None
            if not self.is_streaming:
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
            # refresh tick (privacy OFF). Also skip when streaming (path-1 live
            # proxy snap.jpg already provides a current frame).
            # The placeholder (1×1 black) does NOT count as a real frame — on a
            # genuine cold start we still want to seed from the event image.
            _has_real_frame = (
                bool(self.cached_image)
                and self.cached_image is not self._PLACEHOLDER_JPEG
            )
            if not image and not self.is_streaming and not _has_real_frame:
                image = await self.coordinator.async_fetch_fresh_event_snapshot(
                    self._cam_id
                )

            if image:
                # Privacy TOCTOU guard: re-read privacy from the live cache
                # immediately before writing _cached_image. The coordinator may
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

        except Exception as err:  # noqa: BLE001 — background refresh across multiple cloud/local fetch + disk-save + state-write paths; any failure here must be logged and swallowed so the periodic refresh loop keeps running
            _LOGGER.debug("%s: image refresh failed: %s", self._display_name, err)
        finally:
            self._refresh_inflight = False
            self._force_image_refresh = False

    # ── Helpers ───────────────────────────────────────────────────────────────
    @property
    def _cam_data(self) -> dict[str, Any]:
        return self.coordinator.data.get(self._cam_id, {})  # type: ignore[no-any-return]

    # ── Streaming state ───────────────────────────────────────────────────────
    @property
    @override
    def is_streaming(self) -> bool:
        """True when a live proxy connection is active AND the RTSP URL is ready.

        Controls the HA camera state: True → "streaming", False → "idle".
        Returning True only when `rtspsUrl` is populated (not just when the
        coordinator's `_live_connections` entry exists) prevents a race that
        broke WebRTC on first stream-start: try_live_connection writes the
        cred-bearing result into `_live_connections` BEFORE pre-warm finishes
        (~25-35 s for Gen2), and only sets `rtspsUrl` after pre-warm completes.
        If `is_streaming` flipped to True at the first write, the camera card's
        `_waitForStreamReady` would observe `cam.state === "streaming"`,
        immediately fire `camera/webrtc/offer`, and HA's go2rtc provider would
        reject with `Camera has no stream source` (because `stream_source()`
        below also gates on `rtspsUrl`). The card then 5-s-timed-out and fell
        back to HLS — which is what made WebRTC look like "only works after a
        browser reload" (after a reload, pre-warm was already done and rtspsUrl
        was present from the first state read). Bug 2026-05-27 Innenbereich.
        """
        live = self.coordinator.live_connections.get(self._cam_id, {})
        if not live:
            return False
        return bool(live.get("rtspsUrl") or live.get("rtspUrl"))

    @property
    @override
    def supported_features(self) -> CameraEntityFeature:
        """Advertise STREAM unless the camera is OFFLINE.

        The HA mobile app uses supported_features to decide whether to render a
        native live-stream view (more-info dialog, picture-glance camera_view:live).
        For an OFFLINE camera there is no stream, so the native view would show a
        black video. Dropping STREAM while OFFLINE makes the app fall back to the
        snapshot (entity_picture) instead. An ONLINE *idle* camera MUST keep STREAM
        so the user can still start a live view (the stream opens on demand) — so
        the gate is on OFFLINE status, NOT on is_streaming and NOT on `available`
        (which stays True for an offline camera: the cloud poll succeeds, the
        camera just reports status OFFLINE). UNKNOWN/missing status keeps STREAM
        (only drop when definitively offline). 2026-06-17.
        """
        status = str(self._cam_data.get("status", "")).upper()
        if status == "OFFLINE":
            return CameraEntityFeature(0)
        return CameraEntityFeature.STREAM

    @property
    @override
    def is_recording(self) -> bool:
        return False

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
        await self.coordinator.async_put_camera(
            self._cam_id,
            "motion",
            {"enabled": True, "motionAlarmConfiguration": sensitivity},
        )
        self.hass.async_create_task(self.coordinator.async_request_refresh())

    @override
    async def async_disable_motion_detection(self, **kwargs: Any) -> None:
        """Disable motion detection via standard HA camera service."""
        settings = self.coordinator.motion_settings(self._cam_id)
        sensitivity = (
            settings.get("motionAlarmConfiguration", "HIGH") if settings else "HIGH"
        )
        await self.coordinator.async_put_camera(
            self._cam_id,
            "motion",
            {"enabled": False, "motionAlarmConfiguration": sensitivity},
        )
        self.hass.async_create_task(self.coordinator.async_request_refresh())

    @property
    @override
    def frame_interval(self) -> float:
        """How often (seconds) HA requests a fresh image from this camera.

        When _force_image_refresh is set: 0.1 s — forces immediate cache expiry
        so HA's next proxy request fetches the new snapshot right away.
        When streaming: 1 s — must be shorter than the card's 2 s setInterval so
                        that every card poll triggers a fresh snap.jpg fetch. At 2 s,
                        browser setInterval jitter (±50 ms early) caused HA to return
                        cached frames → alternating 1 s / 3 s gaps instead of 2 s.
        When idle:      IDLE_FRAME_INTERVAL (60 s) — HA calls async_camera_image
                        every 60 s. The actual cloud fetch rate is governed by
                        CLOUD_SNAP_CACHE_TTL (30 s) inside async_camera_image:
                        stale cache → return cached immediately + bg refresh.
                        snapshot_interval (default 1800 s) controls the proactive
                        background refresh in _handle_coordinator_update, not this.
        """
        if self._force_image_refresh:
            return 0.1
        if self.is_streaming:
            return 1.0
        return float(IDLE_FRAME_INTERVAL)

    @property
    def _token(self) -> str:
        return self._entry.data.get("bearer_token", "")  # type: ignore[no-any-return]

    # ── HA metadata ───────────────────────────────────────────────────────────
    @property
    @override
    def brand(self) -> str:
        return "Bosch"

    @property
    @override
    def model(self) -> str:
        return self._model  # type: ignore[no-any-return]

    @property
    @override
    def available(self) -> bool:
        # Firmware install reboots the camera (3–7 min). Mark unavailable so
        # automations and the UI don't poll a dead endpoint or surface stale
        # snapshots as live state.
        is_updating = getattr(self.coordinator, "is_updating", None)
        if is_updating is not None and is_updating(self._cam_id):
            return False
        if self.coordinator.last_update_success:
            return True
        # Cloud poll failed. Inside a KNOWN active Bosch maintenance window the
        # cloud flaps for minutes (Connect refused → ~3 min → recover) while the
        # LOCAL datapath (TLS proxy + RTSP) keeps serving frames. Keep a
        # locally-streaming camera available so the UI/automations don't churn
        # through unavailable on every cloud dip — local snapshot + live stream
        # stay functional. Verified live 2026-06-16 maintenance window.
        return self._local_available_during_cloud_outage()

    def _local_available_during_cloud_outage(self) -> bool:
        """True only when the cloud poll failed but this camera is still locally serviceable.

        Only true inside a known active maintenance window. Three guards,
        ALL required: an active camera-relevant Bosch maintenance
        window, a positive LAN-TCP reachability for this cam, and an established
        local live session (rtsps/rtsp URL ready). Anything unknown/absent →
        False, so we fall back to the cloud coordinator's availability. Must
        never raise — `available` is read on every state-machine update.
        """
        coord = self.coordinator
        mw = getattr(coord, "maintenance_cache", None)
        if mw is None or not getattr(mw, "camera_relevant", False):
            return False
        try:
            if mw.state() != "active":
                return False
        except TypeError, ValueError:
            return False
        is_lan_reachable = getattr(coord, "is_lan_reachable", None)
        if is_lan_reachable is None or is_lan_reachable(self._cam_id) is not True:
            return False
        # Established local live session for THIS cam (mirrors `is_streaming`).
        return self.is_streaming

    @property
    @override
    def device_info(self) -> DeviceInfo:
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
        cam_data = self._cam_data
        events = cam_data.get("events", [])
        latest = events[0] if events else {}
        live = cam_data.get("live", {})
        rtsps_url = live.get("rtspsUrl", live.get("rtspUrl", ""))
        # [S2] Evaluate is_streaming once — property does a dict lookup each time
        is_streaming = self.is_streaming
        # Stream status for dashboard display
        fell_back = self.coordinator.stream_fell_back.get(self._cam_id, False)
        err_count = self.coordinator.stream_error_count.get(self._cam_id, 0)
        if self.coordinator.is_stream_warming(self._cam_id):
            stream_status = "warming_up"
        elif is_streaming:
            stream_status = "streaming (REMOTE fallback)" if fell_back else "streaming"
        elif self._cam_id in self.coordinator.live_connections:
            stream_status = "connecting"
        else:
            stream_status = "idle"

        info = cam_data.get("info", {})
        bosch_priority = info.get("priority")
        attrs = {
            "camera_id": self._cam_id,
            "status": cam_data.get("status", "UNKNOWN"),
            "stream_status": stream_status,
            "streaming_state": "active" if is_streaming else "idle",  # [S2] local var
            "last_event": latest.get("timestamp", "")[:19],
            "event_type": latest.get("eventType", ""),
            "model_name": self._model_name,
            "hardware_version": self.hw_version,
            "firmware": self._fw,
            "mac": self._mac,
            "live_rtsps": _redact_rtsp_creds(rtsps_url),
            "live_proxy": live.get("proxyUrl", ""),
            "stream_errors": err_count,
            # Bosch-app camera order. Mirrors the float priority returned by
            # GET /v11/video_inputs (settable via PUT /v11/video_inputs/order).
            # The overview card reads this when `use_bosch_sort: true` so the
            # HA layout matches the Bosch app order.
            "bosch_priority": bosch_priority,
        }
        if rtsps_url:
            attrs["stream_url"] = _redact_rtsp_creds(rtsps_url)
        # bufferingTime from PUT /connection (LOCAL=500ms, REMOTE=1000ms)
        # — Bosch-server-side hint, NOT the player buffer. Display only.
        live_conn = self.coordinator.live_connections.get(self._cam_id, {})
        bt = live_conn.get("_bufferingTime")
        if bt is not None:
            attrs["buffering_time_ms"] = bt
            attrs["connection_type"] = live_conn.get("_connection_type", "REMOTE")
        # [S2] Single get_options() call for all option reads in this method
        entry_opts = get_options(self._entry)
        # Player-side buffer profile — read by the Lovelace card to configure
        # hls.js. Mode → (liveSyncDurationCount, liveMaxLatencyDurationCount,
        # maxBufferLength, lowLatencyMode) is mapped client-side.
        attrs["live_buffer_mode"] = entry_opts.get("live_buffer_mode", "balanced")
        # Card auto-play default — collapses any non-canonical value to "lan"
        # so a typo or stale option from a previous version never disables
        # stream start. Per-card YAML `auto_play` still overrides this.
        mode = entry_opts.get("auto_play_default", "lan")
        attrs["auto_play_default"] = mode if mode in AUTO_PLAY_DEFAULT_VALUES else "lan"
        # Camera-side timestamp overlay (burned-in date/time, bottom-right of
        # the video frame). The card reads this to hide its own last-event
        # glass pill — otherwise the user sees two timestamps stacked, one
        # burned-in by the camera and one drawn by the card. Defensive
        # getattr covers test stubs that lack the cache.
        ts_cache = getattr(self.coordinator, "timestamp_cache", None)
        if ts_cache is not None:
            ts_overlay = ts_cache.get(self._cam_id)
            if ts_overlay is not None:
                attrs["camera_timestamp_overlay"] = bool(ts_overlay)
        return attrs

    # ── Live stream ───────────────────────────────────────────────────────────
    @callback  # HA @callback is untyped (no py.typed)
    @override
    def close_webrtc_session(self, session_id: str) -> None:
        """Close a WebRTC session — no-op for unknown / never-established sessions.

        HA's go2rtc provider stores sessions in a dict keyed by session_id and
        calls ``dict.pop(session_id)`` (without a default) in ``async_close_session``.
        When privacy mode is ON, ``async_handle_async_webrtc_offer`` calls
        ``_update_stream_source`` which raises HomeAssistantError (no stream source),
        so the session is *never inserted* into ``go2rtc._sessions``.  However the
        websocket handler already registered
        ``partial(camera.close_webrtc_session, session_id)`` as a subscription
        cleanup before the offer was even forwarded — so when the client
        disconnects, ``async_handle_close`` calls this method for a session_id that
        go2rtc never tracked, causing a KeyError that HA logs at ERROR level:

            "Error unsubscribing from subscription: functools.partial(
             <bound method Camera.close_webrtc_session …>, '<session_id>')"

        Fix: delegate to the base class (which calls provider.async_close_session)
        inside a try/except that silences KeyError.  All other exceptions (e.g.
        RuntimeError from a closed event-loop) still propagate so real bugs
        remain visible.

        Regression test: tests/test_close_webrtc_session.py
        """
        try:
            super().close_webrtc_session(session_id)
        except KeyError:
            # Session was never established (e.g. privacy mode was ON when the
            # WebRTC offer arrived and go2rtc bailed before inserting it into
            # its _sessions dict).  Silently discard — there is nothing to close.
            _LOGGER.debug(
                "%s: close_webrtc_session(%s) — session not found, already closed or "
                "never established (privacy mode?); ignoring",
                self._display_name,
                session_id,
            )

    @override
    async def async_create_stream(self) -> Any:
        """Auto-open live connection when play_stream / Cast is requested.

        HA calls this when camera.play_stream is invoked (e.g. Cast to Chromecast).
        Without the override stream_source() returns None with no active session
        → async_create_stream() returns None → HA logs
        "does not support play stream service" (observed 2026-05-09 19:02 CEST).

        When privacy mode is ON the live connection is intentionally blocked.
        We raise HomeAssistantError so HA surfaces a meaningful message instead of
        the generic "does not support play stream service".
        """
        if not self.coordinator.live_connections.get(self._cam_id):
            # Privacy mode gate: do not even attempt a live connection
            shc = self.coordinator.shc_state_cache.get(self._cam_id, {})
            if shc.get("privacy_mode") is True:
                raise HomeAssistantError(
                    f"{self._display_name}: stream unavailable — privacy mode is ON"
                )
            _LOGGER.debug(
                "%s: play_stream — auto-opening live connection", self._display_name
            )
            result = await self.coordinator.try_live_connection(self._cam_id)
            if result is STREAM_START_SKIPPED:
                # Another start for this camera is already in flight — it will
                # populate the session. Don't warn (not a failure); fall through
                # to the pre-warm wait below, which polls until rtspsUrl is set.
                _LOGGER.debug(
                    "%s: play_stream — coalescing into an in-progress start",
                    self._display_name,
                )
            elif not result:
                _LOGGER.warning(
                    "%s: play_stream — live connection failed", self._display_name
                )
                return None
            else:
                self.coordinator.async_update_listeners()
        # Pre-warm race (observed 2026-05-17 05:16:14 UTC for bosch_innenbereich):
        # coordinator sets _live_connections[cam_id] BEFORE the LOCAL pre-warm
        # populates rtspsUrl. During that window stream_source() intentionally
        # returns None — but super().async_create_stream() reads stream_source()
        # and returns None too, which HA core surfaces as the misleading
        # "does not support play stream service". Wait for warming to clear
        # (rtspsUrl gets populated at the same point) so super() reads a valid URL.
        if not await self._wait_for_prewarm("play_stream"):
            return None
        return await super().async_create_stream()

    async def _wait_for_prewarm(self, caller: str) -> bool:
        """Poll until LOCAL pre-warm clears (rtspsUrl populated), or time out.

        Shared by async_create_stream() (HLS/Cast path) and
        async_handle_async_webrtc_offer() (native app / go2rtc path) — both read
        stream_source() right after this returns, and stream_source() only
        returns a URL once pre-warm has cleared. Without this wait, a WebRTC
        offer made mid-warm-up (MOBILE_BACKLOG item, ~25-35s black screen in the
        native HA more-info view) fails immediately instead of waiting like the
        card's own JS retry already does.
        """
        if self._cam_id not in self.coordinator.stream_warming:
            return True
        cfg = self.coordinator.get_model_config(self._cam_id)
        deadline = time.monotonic() + cfg.min_total_wait + 5
        while self._cam_id in self.coordinator.stream_warming:
            if time.monotonic() > deadline:
                _LOGGER.warning(
                    "%s: %s — pre-warm did not complete within %ds",
                    self._display_name,
                    caller,
                    cfg.min_total_wait + 5,
                )
                return False
            await asyncio.sleep(0.5)
        return True

    @override
    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Auto-open a live connection and wait for LOCAL pre-warm before delegating.

        Delegates to the go2rtc provider once pre-warm has settled. Unlike
        async_create_stream() (Cast/HLS path), this native-WebRTC
        entry point never had an auto-open guard: a camera whose "Live
        Stream" switch was never turned on (e.g. right after first setup)
        has no active session, so stream_source() stays None and go2rtc
        raised "Camera does not support WebRTC" for a first-time user simply
        opening the native more-info dialog — no image/stream at all,
        reported by a new user on community.simon42.com. Mirrors the
        auto-open already done in async_create_stream().

        Also: wait for LOCAL pre-warm before delegating to the go2rtc
        provider. Without this, a native WebRTC offer (HA Companion app /
        more-info dialog) arriving while the camera is still warming up hits
        stream_source() returning None with no retry — up to ~35s of black
        screen (MOBILE_BACKLOG). The custom card already retries client-side
        via _waitForStreamReady(); the native path had no equivalent.
        """
        if not self.coordinator.live_connections.get(self._cam_id):
            shc = self.coordinator.shc_state_cache.get(self._cam_id, {})
            if shc.get("privacy_mode") is True:
                raise HomeAssistantError(
                    f"{self._display_name}: stream unavailable — privacy mode is ON"
                )
            _LOGGER.debug(
                "%s: webrtc_offer — auto-opening live connection", self._display_name
            )
            result = await self.coordinator.try_live_connection(self._cam_id)
            if result is STREAM_START_SKIPPED:
                _LOGGER.debug(
                    "%s: webrtc_offer — coalescing into an in-progress start",
                    self._display_name,
                )
            elif not result:
                _LOGGER.warning(
                    "%s: webrtc_offer — live connection failed", self._display_name
                )
            else:
                self.coordinator.async_update_listeners()
        await self._wait_for_prewarm("webrtc_offer")
        await super().async_handle_async_webrtc_offer(
            offer_sdp, session_id, send_message
        )

    @override
    async def stream_source(self) -> str | None:
        """Return RTSP URL when a live connection has been opened.

        LOCAL streams use a local TLS proxy (rtsp://127.0.0.1:PORT/...) so
        FFmpeg can connect via plain TCP while the proxy handles TLS to the camera.
        REMOTE streams use rtsps:// directly (Bosch cloud proxy has valid certs).

        Returns None when no live session is active (switch is OFF).
        Always reads from _live_connections (real-time) instead of coordinator
        data cache to avoid stale URLs after session renewal or mode switch.
        """
        # Read from _live_connections (updated immediately) instead of
        # coordinator data cache (updated on next refresh cycle)
        live = self.coordinator.live_connections.get(self._cam_id, {})
        if not live:
            return None
        url: str | None = live.get("rtspsUrl") or live.get("rtspUrl") or None
        if not url:
            return None
        # LOCAL streams go through our TLS proxy (plain TCP → TLS). HA 2026.4 /
        # FFmpeg Lavf 62 rejects the UDP→TCP transport rewrite the proxy used to
        # do, so we force TCP interleaved on SETUP. REMOTE streams go directly to
        # the Bosch cloud proxy via rtsps:// and must use the FFmpeg default
        # (UDP) — forcing TCP on REMOTE breaks Gen1 Eyes Outdoor cloud streams.
        is_local = live.get("_connection_type") == "LOCAL"
        self.stream_options = {"rtsp_transport": "tcp"} if is_local else {}
        # Audio track is ALWAYS kept in the stream now — switch.<cam>_audio is a
        # card-side mute preference (applied to video.muted), not a track toggle.
        # Stripping it here on a muted-at-start session would leave no track to
        # unmute. The track stays (≈ negligible bandwidth). 2026-06-01.
        return url

    # ── RCP thumbnail fallback ────────────────────────────────────────────────
    def _yuv422_to_jpeg(self, data: bytes) -> bytes | None:
        """Convert a 320×180 YUV422 (YUYV) raw frame to JPEG bytes using numpy+Pillow."""
        try:
            import io

            import numpy as np
            from PIL import Image

            if len(data) != 320 * 180 * 2:
                return None
            # YUYV interleaved: Y0 U Y1 V per 4 bytes = 2 pixels
            raw = np.frombuffer(data, dtype=np.uint8).reshape(180, 320, 2)
            y = raw[:, :, 0].astype(np.float32)
            # U/V are at alternating positions in the second byte channel
            uv_plane = raw[:, :, 1].astype(np.float32)
            # U at even columns, V at odd columns
            u_half = uv_plane[:, 0::2]  # shape (180, 160)
            v_half = uv_plane[:, 1::2]  # shape (180, 160)
            u = np.repeat(u_half, 2, axis=1) - 128.0  # (180, 320)
            v = np.repeat(v_half, 2, axis=1) - 128.0  # (180, 320)
            # [S6] Pre-allocate single float32 output; single np.clip pass on the
            # whole array instead of 3 separate clip+astype chains (saves 4 temp arrays)
            rgb_f = np.empty((180, 320, 3), dtype=np.float32)
            rgb_f[:, :, 0] = y + 1.402 * v  # R
            rgb_f[:, :, 1] = y - 0.344136 * u - 0.714136 * v  # G
            rgb_f[:, :, 2] = y + 1.772 * u  # B
            np.clip(rgb_f, 0, 255, out=rgb_f)
            rgb = rgb_f.astype(np.uint8)
            img = Image.fromarray(rgb, mode="RGB")
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            return buf.getvalue()
        except ImportError, ValueError, OSError:
            return None

    async def _async_rcp_thumbnail(self) -> bytes | None:
        """Fetch a thumbnail via RCP, falling back from JPEG to raw YUV422.

        Tries 320×180 JPEG (0x099e) first, then falls back to 320×180
        YUV422 raw frame (0x0c98) converted to JPEG. Resolution confirmed via RCP 0x0a88 READ (returns 0x00000140/0x000000B4 = 320×180).
        Uses the cached live proxy connection (if available) to reach the
        camera's RCP endpoint. Much faster than snap.jpg (~instant vs ~1.5 s)
        and used as a fallback when the proxy snap.jpg fetch fails.
        """
        live = self.coordinator.live_connections.get(self._cam_id, {})
        urls = live.get("urls", [])
        if not urls:
            return None

        # urls[0] = "proxy-NN.live.cbs.boschsecurity.com:42090/{hash}"
        parts = urls[0].split("/", 1)
        if len(parts) != 2:
            return None
        proxy_host = parts[0]
        proxy_hash = parts[1]

        session_id = await self.coordinator.get_cached_rcp_session(
            proxy_host, proxy_hash
        )
        if not session_id:
            return None

        rcp_base = f"https://{proxy_host}/{proxy_hash}/rcp.xml"

        # Try 320×180 JPEG via RCP 0x099e (resolution confirmed by 0x0a88 = 320×180)
        raw: bytes | None = await self.coordinator.rcp_read(
            rcp_base, "0x099e", session_id
        )
        if raw and raw[:2] == b"\xff\xd8":
            _LOGGER.debug(
                "%s: Using RCP thumbnail fallback (320×180) — %d bytes",
                self._display_name,
                len(raw),
            )
            return raw

        # Fallback: 320×180 YUV422 raw frame → convert to JPEG
        raw = await self.coordinator.rcp_read(rcp_base, "0x0c98", session_id)
        if raw and len(raw) == 115200:
            jpeg = self._yuv422_to_jpeg(raw)
            if jpeg:
                _LOGGER.debug(
                    "%s: Using RCP YUV422 fallback (320x180) — %d bytes → %d bytes JPEG",
                    self._display_name,
                    len(raw),
                    len(jpeg),
                )
                return jpeg
            _LOGGER.debug(
                "%s: RCP YUV422 conversion failed (0x0c98, %d bytes)",
                self._display_name,
                len(raw),
            )
        elif raw:
            _LOGGER.debug(
                "%s: RCP 0x0c98 unexpected size: %d bytes (expected 115200)",
                self._display_name,
                len(raw),
            )
        return None

    # ── Snapshot image ────────────────────────────────────────────────────────
    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Public entrypoint wrapping the implementation to never let exceptions escape.

        Any uncaught exception still returns a valid (placeholder) JPEG
        instead of letting HA's camera proxy serve a textual `500: Internal
        Server Error` body (26 bytes of plain text in place of an image).
        Observed 2026-04-27 on Gen1 cams during the pre-warm transition: while
        `_live_connections[cam_id]` had a partial entry but no proxyUrl yet,
        an unhandled exception path in `_async_camera_image_impl` propagated up
        and HA returned 500. Lovelace's `<img>` element rendered the literal
        text bytes as a brown error frame on every camera card sharing the
        same broken endpoint, making it look like cross-camera bleed.
        """
        try:
            result = await self._async_camera_image_impl(width, height)
            jpeg = result or self._PLACEHOLDER_JPEG
        except asyncio.CancelledError:
            raise  # let cancellation propagate cleanly
        except Exception as err:  # noqa: BLE001 — outer entrypoint guard: any uncaught exception from the fallback cascade must still yield a valid placeholder JPEG instead of HA's camera proxy serving a raw 500 body (see docstring)
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
        """Return the best available JPEG snapshot, tried in this order.

        0. MJPEG inst=3 LAN snapshot (Gen2 opt-in) — when use_mjpeg_snapshot is
           enabled: FFmpeg subprocess captures one frame from RTSP inst=3.
           Requires Gen2 hardware + cached LOCAL Digest credentials.
           ~150-300 ms on healthy LAN. Falls through on any error.
        1. Cloud proxy live snap  — if a live connection has been opened
           (proxy-NN.live.cbs.boschsecurity.com snap.jpg, no auth needed)
           Updated every coordinator tick while live switch is ON.
           1b. RCP thumbnail fallback — 320×180 JPEG via RCP 0x099e, used when
               snap.jpg fetch fails with any error (timeout, network, etc.)
        2. Cloud proxy on-demand  — PUT /connection REMOTE + RCP 0x099e / snap.jpg.
           If no cached image: fetches fresh synchronously (~3 s for snap.jpg,
           ~100 ms for RCP thumbnail when width <= 640).
           If cached image is older than CLOUD_SNAP_CACHE_TTL (30 s): fetches
           fresh synchronously so the user always sees a current image.
        3. Cached image           — fallback when cloud fetch fails (e.g. CAMERA_360
           whose REMOTE snap.jpg returns 401; refreshed via _async_trigger_image_refresh
           using LOCAL connection).
        4. Latest event snapshot  — last resort on very first startup before any
           cloud fetch has completed.

        The card calls trigger_snapshot on page load / tab switch / 60s timer,
        which sets _force_image_refresh=True (frame_interval → 0.1s) and fetches
        a fresh image via _async_trigger_image_refresh. This ensures HA's camera
        proxy serves the fresh image on the next request instead of its 60s cache.

        width/height: passed by HA when the card requests ?width=N. We use this to
        prefer the 320×180 RCP thumbnail on mobile/small displays (avoids 150 KB
        snap.jpg when the card only needs a 400 px thumbnail).
        """
        # Verifying Bosch-cloud session: REMOTE proxy snap.jpg fetches below are
        # TLS-validated against the pinned Bosch CA. The LOCAL Digest paths pass
        # ssl=False per request (camera LAN IP, self-signed) which overrides this
        # session's connector for those calls only.
        session = await async_get_bosch_cloud_session(self.hass)
        token = self._token
        headers_bearer = {"Authorization": f"Bearer {token}", "Accept": "*/*"}
        # True when card requests a mobile/thumbnail-sized image
        prefer_small = width is not None and width <= 640
        _LOGGER.debug(
            "%s: snapshot fallback chain start (worst-case budget %ds)",
            self._display_name,
            SNAPSHOT_FALLBACK_MAX_BUDGET_SEC,
        )

        # ── 0. MJPEG inst=3 snapshot (Gen2 opt-in, LAN-only) ─────────────────
        # When use_mjpeg_snapshot is enabled: capture one JPEG frame directly
        # from the camera's RTSP inst=3 stream via FFmpeg subprocess.
        # Requires Gen2 hardware and valid LOCAL Digest credentials cached by
        # the coordinator from the most recent PUT /connection.
        # Estimated latency: ~150-300 ms on LAN (vs ~500-1500 ms cloud-proxy).
        # Falls through silently on any error — existing paths take over.
        # [S1] Check the flag directly on entry.options before allocating the merged
        # options dict — avoids dict(DEFAULT_OPTIONS)+update() on every image call
        # (default is False, so this fast-path fires for all standard installs).
        if self._entry.options.get("use_mjpeg_snapshot", False):
            opts = get_options(self._entry)  # full merge only when feature is enabled
            model_cfg = get_model_config(self.hw_version)  # [S4] module-level import
            if model_cfg.generation >= 2:
                creds = self.coordinator.local_creds_cache.get(self._cam_id)
                # cbs creds rotate ~60 s after each PUT /connection without
                # heartbeat. Skip MJPEG when creds are stale — FFmpeg would
                # fail "Invalid data found when processing input" otherwise.
                # Threshold 45 s keeps a safety margin.
                creds_age = (
                    time.monotonic() - creds.get("ts", float("-inf"))
                    if creds
                    else float("inf")
                )
                if creds and creds_age < 45.0:
                    _local_user_m = creds.get("user", "")
                    _local_pass_m = creds.get("password", "")
                    _local_host_m = creds.get("host", "")
                    _local_port_m = int(creds.get("port", 443))
                    if _local_user_m and _local_pass_m and _local_host_m:
                        mjpeg_data = await fetch_mjpeg_snapshot(
                            _local_host_m,
                            _local_port_m,
                            _local_user_m,
                            _local_pass_m,
                            timeout=float(
                                opts.get("mjpeg_snapshot_timeout", TIMEOUT_SNAP)
                            ),
                        )
                        if mjpeg_data:
                            self.cached_image = mjpeg_data
                            self.last_image_fetch = time.monotonic()
                            return mjpeg_data

        # ── 1. Cloud proxy live snapshot (active live-stream session) ─────────
        live = self.coordinator.live_connections.get(self._cam_id, {})
        proxy_url = live.get("proxyUrl", "")
        if proxy_url:
            # LOCAL connection: snap.jpg requires HTTP Digest auth
            if live.get("_connection_type") == "LOCAL":
                local_user = live.get("_local_user", "")
                local_pass = live.get("_local_password", "")
                if local_user and local_pass:
                    data: bytes | None = None
                    try:
                        # Tightened from 12 s to 6 s: HA's CameraImageView wraps
                        # async_camera_image() with CAMERA_IMAGE_TIMEOUT (10 s);
                        # 12 s + 10 s aiohttp fallback below = >22 s, well over
                        # HA's outer timeout. HA cancels mid-flight → image=None
                        # → HomeAssistantError → 26-byte "500: Internal Server
                        # Error" body rendered as a brown placeholder on the
                        # camera card. 6 s is enough for a healthy LAN Digest
                        # round-trip; if it fails, return cached/placeholder
                        # immediately rather than racing HA's outer timeout.
                        async with asyncio.timeout(6):
                            async with await async_digest_request(
                                session,
                                "GET",
                                proxy_url,
                                local_user,
                                local_pass,
                                timeout=TIMEOUT_SNAP,
                                ssl=False,
                            ) as resp:
                                if resp.status == 200 and "image" in resp.headers.get(
                                    "Content-Type", ""
                                ):
                                    data = await resp.read()
                    except (TimeoutError, aiohttp.ClientError, ValueError) as err:
                        # ValueError: malformed/missing WWW-Authenticate header
                        # from auth_utils.async_digest_request — forum 998974/15.
                        _LOGGER.debug("LOCAL snap via proxy failed: %s", err)
                        data = None
                    if data:
                        self.cached_image = data
                        self.last_image_fetch = time.monotonic()
                        _LOGGER.debug(
                            "%s: LOCAL live snap %d bytes",
                            self._display_name,
                            len(data),
                        )
                        return self.cached_image
                    # LOCAL conn: skip the aiohttp fallback below. The proxy_url
                    # for LOCAL is `https://<lan-ip>:443/snap.jpg` which requires
                    # the Digest auth we just tried — aiohttp without auth would
                    # 401 in another ~10 s burning HA's outer budget. Go straight
                    # to cached image / placeholder via the final return.
                    return self.cached_image or self._PLACEHOLDER_JPEG
            renew_after_status: int | None = None
            try:
                async with asyncio.timeout(10):
                    async with session.get(proxy_url) as resp:
                        ct = resp.headers.get("Content-Type", "")
                        if resp.status == 200 and "image" in ct:
                            data = await resp.read()
                            if data:
                                self.cached_image = data
                                self.last_image_fetch = time.monotonic()
                                _LOGGER.debug(
                                    "%s: live proxy snapshot %d bytes",
                                    self._display_name,
                                    len(self.cached_image),
                                )
                                return self.cached_image
                        elif resp.status == 404:
                            # 404 = proxy URL expired. Defer the renewal to AFTER
                            # this snapshot timeout closes (see below).
                            renew_after_status = 404
                        elif resp.status in (401, 403):
                            opened_at = self.coordinator.live_opened_at.get(
                                self._cam_id, float("-inf")
                            )
                            age = time.monotonic() - opened_at
                            if age >= LIVE_SESSION_TTL:
                                renew_after_status = resp.status
                            else:
                                _LOGGER.debug(
                                    "%s: proxy snapshot %d (age %.0fs) — keeping session (camera requires auth for snap.jpg)",
                                    self._display_name,
                                    resp.status,
                                    age,
                                )
                # Renew OUTSIDE the 10s snapshot timeout: try_live_connection can
                # take up to ~100s (PUT /connection + LOCAL pre-warm) and must not
                # be cancelled mid-flight by the snapshot budget — which previously
                # aborted every renewal on a slow camera (bug-hunt 2026-06-02).
                if renew_after_status is not None:
                    opened_at = self.coordinator.live_opened_at.get(
                        self._cam_id, float("-inf")
                    )
                    age = time.monotonic() - opened_at
                    _LOGGER.debug(
                        "%s: proxy snapshot %d (age %.0fs) — renewing live connection",
                        self._display_name,
                        renew_after_status,
                        age,
                    )
                    new_live = await self.coordinator.try_live_connection(self._cam_id)
                    if new_live is STREAM_START_SKIPPED:
                        # Another start for this camera is already in flight — it
                        # will publish the session. This is NOT a failure and the
                        # in-flight start owns _live_connections/_live_opened_at:
                        # popping here would delete a concurrent renewal's fresh
                        # session and kill the stream + any Frigate front-door
                        # reading its creds. Leave the state untouched. This was
                        # the one snapshot-recovery call site missing the
                        # `is STREAM_START_SKIPPED` guard used at camera.py play_stream
                        # and switch.py turn-on. (bug-hunt 2026-07-01)
                        _LOGGER.debug(
                            "%s: snapshot renewal coalesced into an in-progress "
                            "start — keeping live session",
                            self._display_name,
                        )
                    elif new_live:
                        new_proxy_url = new_live.get("proxyUrl", "")
                        if new_proxy_url:
                            try:
                                async with asyncio.timeout(10):
                                    async with session.get(new_proxy_url) as retry_resp:
                                        ct2 = retry_resp.headers.get("Content-Type", "")
                                        if retry_resp.status == 200 and "image" in ct2:
                                            data = await retry_resp.read()
                                            if data:
                                                self.cached_image = data
                                                self.last_image_fetch = time.monotonic()
                                                return self.cached_image
                            except TimeoutError, aiohttp.ClientError:
                                pass
                    elif renew_after_status in (401, 403):
                        # Renewal of an expired session failed — clear so
                        # is_streaming goes to False cleanly. (A 404 renewal that
                        # fails keeps the connection: the URL may recover.)
                        _LOGGER.debug(
                            "%s: session renewal failed — clearing",
                            self._display_name,
                        )
                        self.coordinator.live_connections.pop(self._cam_id, None)
                        self.coordinator.live_opened_at.pop(self._cam_id, None)
            except TimeoutError, aiohttp.ClientError:
                # Any network/timeout error on the live proxy snap.jpg — try RCP thumbnail
                rcp_thumb = await self._async_rcp_thumbnail()
                if rcp_thumb:
                    self.cached_image = rcp_thumb
                    self.last_image_fetch = time.monotonic()
                    return self.cached_image

        # ── 2. Cloud proxy on-demand snapshot (PUT /connection REMOTE → snap.jpg) ──
        # Primary snapshot method for idle cameras. Two modes:
        #
        # a) No cached image yet (first load / cache empty): fetch synchronously so
        #    HA has something to serve immediately. ~3s on cold cache.
        #
        # b) Cached image exists but is stale (> CLOUD_SNAP_CACHE_TTL): fetch fresh
        #    synchronously so the user always sees a current image. The card triggers
        #    this via trigger_snapshot service which sets _force_image_refresh, so
        #    HA's frame_interval cache is bypassed and the fresh image is served.
        #
        # Skip when streaming — opening a new PUT /connection kills the active RTSP session.
        if not self.is_streaming:
            now = time.monotonic()
            cache_stale = (now - self.last_image_fetch) >= CLOUD_SNAP_CACHE_TTL
            if (
                not self.cached_image or self.cached_image is self._PLACEHOLDER_JPEG
            ) and cache_stale:
                # First load — must wait synchronously. The placeholder is a real
                # (truthy) 1×1 black JPEG, so `not self.cached_image` alone never
                # fires while we still hold it — use the identity check too (mirror
                # of _async_trigger_image_refresh). Without this, a cold-boot proxy
                # request (HA Companion app on restart, before the async disk-restore
                # in async_added_to_hass completes) was served the black placeholder
                # instead of fetching a real frame → "black image on mobile".
                # The `and cache_stale` gate is the backoff: a persistently-offline
                # camera (every fetch fails, placeholder stays) would otherwise
                # re-enter this slow RCP+REMOTE+LOCAL chain on EVERY proxy request,
                # since the placeholder identity is true regardless of staleness.
                # On true first load _last_image_fetch is the boot sentinel, so
                # cache_stale is True and this still fetches immediately.
                # For mobile/thumbnail requests (width ≤ 640): try RCP 0x099e first
                # (320×180 JPEG, ~3 KB, ~100 ms with cached session) before the slow
                # full proxy path (PUT /connection + snap.jpg, ~3 s cold).
                if prefer_small:
                    rcp_img = await self._async_rcp_thumbnail()
                    if rcp_img:
                        self.cached_image = rcp_img
                        self.last_image_fetch = now
                        _LOGGER.debug(
                            "%s: RCP thumbnail (first load, prefer_small) — %d bytes",
                            self._display_name,
                            len(rcp_img),
                        )
                        return rcp_img
                fresh: bytes | None = await self.coordinator.async_fetch_live_snapshot(
                    self._cam_id
                )
                if not fresh:
                    # REMOTE snap.jpg returns 401 on CAMERA_360 — try LOCAL Digest fallback
                    fresh = await self.coordinator.async_fetch_live_snapshot_local(
                        self._cam_id
                    )
                if fresh:
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
                # don't re-run the slow RCP+REMOTE+LOCAL chain on every proxy request;
                # retry after CLOUD_SNAP_CACHE_TTL. Mirrors the stale branch below.
                # Falls through to 2b / cached / event-snapshot fallback.
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
                if prefer_small:
                    rcp_img = await self._async_rcp_thumbnail()
                    if rcp_img:
                        self.cached_image = rcp_img
                        self.last_image_fetch = now
                        return rcp_img
                fresh2: bytes | None = await self.coordinator.async_fetch_live_snapshot(
                    self._cam_id
                )
                if not fresh2:
                    # REMOTE snap.jpg returns 401 on CAMERA_360 — try LOCAL Digest fallback
                    fresh2 = await self.coordinator.async_fetch_live_snapshot_local(
                        self._cam_id
                    )
                if fresh2:
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

        # ── 2b. LOCAL snap.jpg with cached Digest creds (cloud-outage fallback) ──
        # When the Bosch cloud or auth server is unreachable, PUT /connection
        # REMOTE fails — but we may still have valid LOCAL creds from the
        # previous session (cached in coordinator.local_creds_cache). Try
        # fetching snap.jpg directly from the camera's LAN IP using those
        # creds before giving up. Digest creds are ephemeral (camera rotates
        # them on reboot) but usually stable for minutes to hours.
        creds = self.coordinator.local_creds_cache.get(self._cam_id)
        # Skip while streaming: a LOCAL Digest snap.jpg opens a second HTTP
        # session against the camera, contending with the Bosch 3-session limit
        # and risking teardown of the active RTSP stream — same reason section 2
        # is gated on `not is_streaming`. The live proxy (section 1) already
        # serves snapshots during a stream; fall through to the cached image.
        if creds and self.coordinator.auth_outage_count > 0 and not self.is_streaming:
            local_user = creds.get("user", "")
            local_pass = creds.get("password", "")
            host = creds.get("host", "")
            port = creds.get("port", 443)
            if local_user and local_pass and host:
                snap_url = f"https://{host}:{port}/snap.jpg?JpegSize=1206"
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
        # _async_trigger_image_refresh keeps this cache warm via LOCAL connection.
        if self.cached_image:
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
                # snapshot fallback cascade (6/10/10/12/10s) — a 20s budget
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
                                ev.get("timestamp", "")[:19],
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
                            ev.get("timestamp", "")[:19],
                        )
            except (TimeoutError, aiohttp.ClientError) as err:
                _LOGGER.debug("%s: event snapshot error: %s", self._display_name, err)

        # Return last cached image if all methods failed
        return self.cached_image or self._PLACEHOLDER_JPEG

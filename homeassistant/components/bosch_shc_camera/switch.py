"""Bosch Smart Home Camera — Switch Platform.

Creates switch entities per camera:
  • {Name} Live Stream  — ON = live stream active, OFF = stopped
                          Turning ON: opens PUT /connection REMOTE, sets stream_source
                          to rtsps://:443 (30fps H.264 + AAC audio).
                          Stays ON until manually turned OFF.
                          Turning OFF clears the session immediately.
                          Default: OFF (no live stream on startup).

  • {Name} Audio        — ON = stream includes audio (AAC), OFF = video-only
                          Affects the rtsps:// URL used by go2rtc / WebRTC.
                          If live stream is active, re-opens the connection.
                          Default: OFF (silent stream; avoids unexpected audio).

  • {Name} Privacy Mode — ON = privacy mode active (camera off / lens covered).
                          Uses Bosch cloud API: PUT /v11/video_inputs/{id}/privacy.
                          No SHC local API needed — works without SHC configured.

  • {Name} Camera Light — ON = camera indicator LED on, OFF = LED off.
                          Only available if camera supports light (featureSupport.light).
                          Uses Bosch cloud API: PUT /v11/video_inputs/{id}/lighting_override.
                          No SHC local API needed — works without SHC configured.

  • {Name} Notifications — ON = notifications enabled (FOLLOW_CAMERA_SCHEDULE or ON_CAMERA_SCHEDULE),
                           OFF = ALWAYS_OFF.
                           Uses Bosch cloud API: PUT /v11/video_inputs/{id}/enable_notifications.
                           State is read from /v11/video_inputs (notificationsEnabledStatus field).
                           Three-state aware: both FOLLOW_CAMERA_SCHEDULE and ON_CAMERA_SCHEDULE
                           are treated as ON. Turning ON always sends FOLLOW_CAMERA_SCHEDULE.
                           No SHC local API needed.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, ClassVar, override
from urllib.parse import urlsplit, urlunsplit

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BoschCameraConfigEntry, BoschCameraCoordinator, get_options
from .cloud_ssl import async_get_bosch_cloud_session
from .const import DOMAIN, STREAM_START_SKIPPED
from .guards import _INDOOR_HW, _get_cam_lock, _is_gen2_indoor, _warn_if_privacy_on
from .models import get_display_name, get_model_config
from .session_state import FloatFieldView
from .shc import _is_gen2

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


def _redact_rtsp_creds(url: str) -> str:
    """Strip userinfo credentials from an RTSP(S) URL before it reaches a log.

    The LOCAL proxy / Digest credentials are embedded in the netloc userinfo
    (``user:password@host``); the rest of the URL (host, port, path, stream
    params) carries no secret. We replace the userinfo with ``***:***`` so the
    line stays useful for debugging without writing credentials to the log —
    HA logs are routinely pasted into forum bug reports. Mirrors the
    never-log-creds principle of the __init__ RTSPS sanitiser (CWE-312).
    """
    if not url:
        return ""
    parsed = urlsplit(url)
    if "@" not in parsed.netloc:
        return url
    host_part = parsed.netloc.rsplit("@", 1)[1]
    return urlunsplit(
        (
            parsed.scheme,
            f"***:***@{host_part}",
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
class _BoschSwitchBase(CoordinatorEntity[BoschCameraCoordinator], SwitchEntity):
    """Shared base for Bosch camera switch entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._cam_id = cam_id
        self._entry = entry

        info = coordinator.data.get(cam_id, {}).get("info", {})
        self._cam_title = info.get("title", cam_id)
        self._model = info.get("hardwareVersion", "CAMERA")
        self._model_name = get_display_name(self._model)
        self._fw = info.get("firmwareVersion", "")
        self._mac = info.get("macAddress", "")

    async def _async_apply_toggle(
        self,
        endpoint: str,
        body: dict[str, Any],
        cache: dict[str, Any],
        set_at: dict[str, float] | FloatFieldView,
        cache_value: Any,
    ) -> None:
        """PUT `endpoint`; on success, cache `cache_value` + stamp `set_at`.

        Shared by the simple boolean-toggle switches (privacy sound,
        timestamp overlay, status LED, alarm arming, …) that were previously
        each copy-pasting this same write→cache→set_at→write_ha_state
        sequence with only the endpoint/body/cache dicts differing. `cache`
        and `set_at` are the coordinator's existing per-feature dicts/views
        passed by reference (other modules read them directly by name), so
        this does not change any external cache identity — only removes the
        duplication of the write sequence itself. `set_at` accepts either a
        bare dict or a `FloatFieldView` (Session-State-Facade Slice 1, see
        session_state.py) — both support `[cam_id] = value`.
        """
        success = await self.coordinator.async_put_camera(self._cam_id, endpoint, body)
        if success:
            cache[self._cam_id] = cache_value
            set_at[self._cam_id] = time.monotonic()
        self.async_write_ha_state()

    def _warn_write_failed(self, feature: str, desired_label: str) -> None:
        """Log a total write failure the cloud setter otherwise swallows.

        The setters (shc.py) never raise — an automation calling into a
        switch must keep running its later steps — so a total failure
        across every fallback path is otherwise invisible: `is_on` still
        reflects the last cached state and the UI just reverts with zero
        explanation (live report 2026-07-07, privacy mode; same discard
        pattern existed here too).
        """
        _LOGGER.warning(
            "%s toggle for %s (%s) failed on all paths — state unchanged",
            feature,
            self._cam_title,
            desired_label,
        )

    @property
    @override
    def available(self) -> bool:
        """Base availability: coordinator running AND camera is ONLINE.

        Prevents automation triggers and service calls from reaching cameras
        that are currently offline or unreachable. Cloud-only switches
        (BoschPrivacyModeSwitch, BoschNotificationsSwitch, notification type
        switches) override this to skip the per-camera online check, since
        those API calls go through the Bosch cloud and succeed even when
        the camera itself is unreachable.
        """
        return (
            self.coordinator.last_update_success
            and self.coordinator.is_camera_online(self._cam_id)
        )

    @property
    @override
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._cam_id)},
            name=f"Bosch {self._cam_title}",
            manufacturer="Bosch",
            model=self._model_name,
            sw_version=self._fw,
            connections={("mac", self._mac)} if self._mac else set(),
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: BoschCameraConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities for each camera."""
    opts = get_options(config_entry)

    coordinator = config_entry.runtime_data
    entities: list[_BoschSwitchBase] = []
    for cam_id in coordinator.data:
        cam_info = coordinator.data[cam_id].get("info", {})
        entities.append(BoschLiveStreamSwitch(coordinator, cam_id, config_entry))
        entities.append(BoschAudioSwitch(coordinator, cam_id, config_entry))
        # Privacy mode — always available via cloud API (no SHC needed)
        entities.append(BoschPrivacyModeSwitch(coordinator, cam_id, config_entry))
        # Camera light — only if cloud API reports featureSupport.light = True.
        # Do NOT fall back to "SHC configured" — cameras without a physical light
        # (e.g. CAMERA_360 indoor) would otherwise get a spurious light switch.
        has_light = cam_info.get("featureSupport", {}).get("light", False)
        if has_light:
            entities.append(BoschCameraLightSwitch(coordinator, cam_id, config_entry))
            entities.append(BoschFrontLightSwitch(coordinator, cam_id, config_entry))
            entities.append(BoschWallwasherSwitch(coordinator, cam_id, config_entry))
        # Notifications — available for all cameras via cloud API
        entities.append(BoschNotificationsSwitch(coordinator, cam_id, config_entry))
        # Motion detection toggle — available for all cameras via cloud API
        entities.append(BoschMotionEnabledSwitch(coordinator, cam_id, config_entry))
        # Record sound toggle — available for all cameras via cloud API
        entities.append(BoschRecordSoundSwitch(coordinator, cam_id, config_entry))
        # Auto-follow — only for cameras with panLimit > 0 (CAMERA_360)
        pan_limit = cam_info.get("featureSupport", {}).get("panLimit", 0)
        if pan_limit:
            entities.append(BoschAutoFollowSwitch(coordinator, cam_id, config_entry))
        # Intercom (two-way audio) — gated on the `enable_intercom` option so
        # the option toggle has actual effect. Legacy users who enabled the
        # entity via the UI keep it (registry already has the entry); new
        # users see nothing until they enable the option explicitly.
        intercom_uid = f"bosch_shc_camera_{cam_id}_intercom"
        intercom_in_registry = (
            er.async_get(hass).async_get_entity_id("switch", DOMAIN, intercom_uid)
            is not None
        )
        if opts.get("enable_intercom", False) or intercom_in_registry:
            entities.append(BoschIntercomSwitch(coordinator, cam_id, config_entry))
        # Privacy sound — only for cameras where the endpoint returns 200 (not 442)
        # Indoor CAMERA_360 (Gen1) + HOME_Eyes_Indoor (Gen2) support it; outdoor returns 442.
        hw_version = cam_info.get("hardwareVersion", "")
        if hw_version in (
            "CAMERA_360",
            "INDOOR",
            "HOME_Eyes_Indoor",
            "CAMERA_INDOOR_GEN2",
        ):
            entities.append(BoschPrivacySoundSwitch(coordinator, cam_id, config_entry))
        # Timestamp overlay — available for all cameras
        entities.append(BoschTimestampSwitch(coordinator, cam_id, config_entry))
        # Status LED — Gen2 cameras only
        if get_model_config(hw_version).generation >= 2:
            entities.append(BoschStatusLedSwitch(coordinator, cam_id, config_entry))
            entities.append(BoschMotionLightSwitch(coordinator, cam_id, config_entry))
            entities.append(BoschAmbientLightSwitch(coordinator, cam_id, config_entry))
            entities.append(
                BoschSoftLightFadingSwitch(coordinator, cam_id, config_entry)
            )
            entities.append(
                BoschIntrusionDetectionSwitch(coordinator, cam_id, config_entry)
            )
        # Notification type toggles — person is cloud AI (all cameras);
        # audio gated on featureSupport.sound (API-reported, not hardcoded by model).
        has_sound = cam_info.get("featureSupport", {}).get("sound", False)
        for ntype in ("movement", "person", "trouble", "cameraAlarm", "troubleEmail"):
            entities.append(
                BoschNotificationTypeSwitch(coordinator, cam_id, config_entry, ntype)
            )
        if has_sound:
            entities.append(
                BoschNotificationTypeSwitch(coordinator, cam_id, config_entry, "audio")
            )
        # Gen2 Audio-Plus sound analytics — glass-break + fire/smoke detection
        # (cloud audioDetectionConfig). Gated on featureSupport.sound; the entity
        # stays unavailable until the camera returns the config (the feature is
        # Audio-Plus subscription-dependent). 2026-06-22.
        if get_model_config(hw_version).generation >= 2 and has_sound:
            entities.append(
                BoschGlassBreakDetectionSwitch(coordinator, cam_id, config_entry)
            )
            entities.append(
                BoschFireAlarmDetectionSwitch(coordinator, cam_id, config_entry)
            )
        # Gen2 Indoor II — alarm system (integrated 75 dB siren)
        if hw_version in ("HOME_Eyes_Indoor", "CAMERA_INDOOR_GEN2"):
            entities.append(
                BoschAlarmSystemArmSwitch(coordinator, cam_id, config_entry)
            )
            entities.append(BoschAlarmModeSwitch(coordinator, cam_id, config_entry))
            entities.append(BoschPreAlarmSwitch(coordinator, cam_id, config_entry))
        # Gen2 panic-alarm — manual siren trigger via PUT /panic_alarm.
        # Gen1 keeps the auto-stop button in button.py (BoschAcousticAlarmButton).
        if get_model_config(hw_version).generation >= 2:
            entities.append(BoschPanicAlarmSwitch(coordinator, cam_id, config_entry))
        # Image rotation 180° — only for indoor cameras (Gen1 360 + Gen2 Indoor II).
        # Outdoor cameras have a fixed mounting orientation by design and don't
        # need this. The switch is purely client-side display state — the card
        # applies CSS transform, the snapshot path applies PIL rotation, and
        # (for Gen1 360) the pan slider sign is inverted.
        if hw_version in _INDOOR_HW:
            entities.append(
                BoschImageRotation180Switch(coordinator, cam_id, config_entry)
            )
        # Mini-NVR recording switch — opt-in via integration option `enable_nvr`.
        # Disabled by default; user enables in options, then toggles per camera.
        if opts.get("enable_nvr", False):
            entities.append(BoschNvrRecordingSwitch(coordinator, cam_id, config_entry))
            # Opt-out for the native FCM-triggered event→clip assembly —
            # default ON (backward compatible); installs that orchestrate
            # their own clip-saving externally can turn this off per camera
            # while the pre-roll ring keeps running for their own consumer.
            entities.append(BoschNvrEventClipSwitch(coordinator, cam_id, config_entry))
        # External stream URL exposure — per-camera opt-in for Frigate / BlueIris users.
        # The switch is always registered (default OFF, disabled in entity registry by
        # default); user enables in HA UI per camera, then the two stream_url sensors
        # populate. Avoids entity-spam on installs that don't need external recorders.
        entities.append(BoschExternalStreamSwitch(coordinator, cam_id, config_entry))
        # Frigate / external-recorder persistent credential-free RTSP endpoints.
        # Two per-camera switches (High = inst=1, Low = inst=2); each publishes
        # its frigate_url_* sensor and starts the always-on front-door on demand.
        # Always registered (default OFF, disabled in entity registry), gated by
        # the global `frigate_endpoints_enabled` option.
        entities.append(BoschFrigateHighSwitch(coordinator, cam_id, config_entry))
        entities.append(BoschFrigateLowSwitch(coordinator, cam_id, config_entry))
    async_add_entities(entities, update_before_add=False)


# ─────────────────────────────────────────────────────────────────────────────
class BoschLiveStreamSwitch(_BoschSwitchBase):
    """Switch: ON = user explicitly requested a live stream, OFF = idle.

    State is driven by the coordinator's `_user_intent_streams` set, NOT
    the internal `_live_connections` dict. HA Core opens streams in the
    background for Lovelace card preload, Cast / `play_stream`, and
    snapshot fetch — each populates `_live_connections` but does not
    reflect explicit user intent. The switch tracks intent separately so
    those auto-opens don't flip the visible state. Reported 2026-05-20.

    Stays ON until manually turned OFF, privacy mode engages, or HA
    restarts (intent is not RestoreEntity-persisted).
    """

    # The (redacted) RTSP/proxy URLs rotate on every reconnect — recording
    # them churns the `state_attributes` table with no history value (HA#39).
    _unrecorded_attributes = frozenset({"rtsps_url", "proxy_snap_url"})

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_live_{cam_id.lower()}"
        self._attr_translation_key = "live_stream"

    @override
    async def async_added_to_hass(self) -> None:
        """Register with the coordinator so `_tear_down_live_stream` can
        push the cleared state to HA immediately. Without the registry the
        UI shows a stale "on" until the next coordinator tick.
        """
        await super().async_added_to_hass()
        self.coordinator.live_stream_entities[self._cam_id] = self

    @override
    async def async_will_remove_from_hass(self) -> None:
        self.coordinator.live_stream_entities.pop(self._cam_id, None)
        await super().async_will_remove_from_hass()

    @property
    @override
    def is_on(self) -> bool:
        """True if the user explicitly turned the live stream on."""
        return self._cam_id in self.coordinator.user_intent_streams

    @property
    @override
    def available(self) -> bool:
        """Unavailable while privacy mode is active or the LOCAL keepalive loop has stalled.

        Also unavailable during firmware install — the camera reboots and no
        stream can start on a rebooting endpoint.
        """
        is_updating = getattr(self.coordinator, "is_updating", None)
        if is_updating is not None and is_updating(self._cam_id):
            return False
        if not super().available:
            return False
        if bool(
            self.coordinator.shc_state_cache.get(self._cam_id, {}).get("privacy_mode")
        ):
            return False
        return not self.coordinator.is_session_stale(self._cam_id)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        live = self.coordinator.live_connections.get(self._cam_id, {})
        conn_type = live.get("_connection_type", "REMOTE") if live else ""
        return {
            "connection_type": conn_type,
            "rtsps_url": _redact_rtsp_creds(live.get("rtspsUrl", "")),
            "proxy_snap_url": live.get("proxyUrl", ""),
        }

    # Minimum seconds between stream ON attempts per camera.
    _STREAM_COOLDOWN = 5

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Open a new live proxy connection."""
        # Block stream start if privacy mode is active (camera shutter is closed)
        if bool(
            self.coordinator.shc_state_cache.get(self._cam_id, {}).get("privacy_mode")
        ):
            raise ServiceValidationError(
                f"Cannot start stream for {self._cam_title} — privacy mode is active. "
                "Turn off privacy mode first.",
            )
        # SENTINEL_RULE: "never stopped" is float("-inf"), not 0 — the prior
        # `last_off > 0` guard worked but was fragile; -inf makes elapsed huge
        # so the first-ever turn-on is never falsely blocked.
        last_off = getattr(self, "_last_stream_off", float("-inf"))
        elapsed = time.monotonic() - last_off
        if elapsed < self._STREAM_COOLDOWN:
            _LOGGER.warning(
                "Stream ON for %s blocked — cooldown %.0fs remaining",
                self._cam_title,
                self._STREAM_COOLDOWN - elapsed,
            )
            return
        _LOGGER.info("Live stream ON for %s", self._cam_title)
        # Mark user intent BEFORE the connection attempt — async_create_stream
        # auto-opens (Cast / play_stream / Lovelace) can race with this turn-on
        # and we want the switch to read "on" immediately while we work.
        self.coordinator.user_intent_streams.add(self._cam_id)
        # No explicit cleanup needed — try_live_connection() sends a new
        # PUT /connection which automatically replaces any stale session.
        result = await self.coordinator.try_live_connection(self._cam_id)
        if result is STREAM_START_SKIPPED:
            # A start for this camera is already in flight (second card, a
            # Lovelace auto-open, or a play_stream racing this user toggle).
            # That start will publish the session — this is NOT a failure.
            # Keep the user intent we set above, do NOT log a failure or
            # record a (false) stream error, and reflect the optimistic
            # "on" state. (Fixes the spurious "Live stream failed" warning
            # seen on concurrent starts, 2026-06-18.)
            _LOGGER.debug(
                "Live stream start for %s coalesced into an in-progress start",
                self._cam_title,
            )
            self.async_write_ha_state()
            return
        if result:
            conn_type = result.get("_connection_type", "REMOTE")
            _LOGGER.info(
                "Live stream active for %s (%s) — %s",
                self._cam_title,
                conn_type,
                _redact_rtsp_creds(result.get("rtspsUrl", "")),
            )
            # Schedule health check — if the LOCAL stream isn't actually
            # producing HLS segments after ~60s and still not after ~120s,
            # record errors and restart. After enough errors the next
            # try_live_connection() falls through to REMOTE automatically
            # via the max_stream_errors gate.
            # Track the task on the coordinator so async_unload_entry cancels
            # it during integration reload; otherwise a stale check from a
            # previous session can fire against a fresh coordinator and start
            # a second renewal loop alongside the user-triggered one.
            if conn_type == "LOCAL":
                hc_task = self.hass.async_create_task(
                    self._stream_health_watchdog(self._cam_id)
                )
                self.coordinator.bg_tasks.add(hc_task)
                hc_task.add_done_callback(self.coordinator.bg_tasks.discard)
        else:
            _LOGGER.warning(
                "Live stream failed for %s — check HA logs", self._cam_title
            )
            # Revert the intent we set before the attempt — the open failed,
            # the switch should not be left at "on" while the underlying
            # session is dead.
            self.coordinator.user_intent_streams.discard(self._cam_id)
            self.coordinator.record_stream_error(self._cam_id)
        self.async_write_ha_state()

    async def _stream_health_watchdog(self, cam_id: str) -> None:
        """Watchdog for a LOCAL stream: verify HA's stream component is
        actually producing HLS output.

        Runs two checks (60s, 120s after the live URL was exposed). At each
        tick:
          * stop early if the stream was turned off or already switched to
            REMOTE — nothing to watch.
          * ask HA's `Stream` object whether it's `available` — that flag
            flips True only when the FFmpeg worker has produced its first
            segment. A Stream object that exists but whose `available` is
            False means FFmpeg started and then died, which is exactly the
            failure mode reported in issue #6 (yellow → brief blue → yellow
            cycle).

        On a healthy tick the watchdog clears the coordinator error counter
        and exits. On a failing tick it records a stream error, tears the
        LOCAL session down, and calls try_live_connection() again — which
        will go directly to REMOTE once `max_stream_errors` is reached.
        Two failed ticks in a row therefore escalate to Cloud within ~2 min
        without any hard-coded time gate.
        """

        def _is_local_active() -> bool:
            live = self.coordinator.live_connections.get(cam_id, {})
            return bool(live) and live.get("_connection_type") == "LOCAL"

        def _stream_health_state() -> str:
            # Three-state classifier so we don't conflate "no consumer yet"
            # with "stream object exists but is unhealthy". Returns:
            #   "no_consumer" — cam_entity.stream is None (frontend never
            #     asked for HLS, FFmpeg never started). Restarting the LOCAL
            #     session does NOT help here; nobody is reading bytes.
            #   "healthy"     — Stream.available is True (worker producing).
            #   "unhealthy"   — Stream object exists but available is False
            #     (FFmpeg started and died, or never produced first segment).
            cam_entity = self.coordinator.camera_entities.get(cam_id)
            if not cam_entity:
                return "no_consumer"
            stream = getattr(cam_entity, "stream", None)
            if stream is None:
                return "no_consumer"
            return (
                "healthy" if bool(getattr(stream, "available", False)) else "unhealthy"
            )

        for idx, delay in enumerate((60, 60)):  # 60s, then another 60s → ~2 min total
            await asyncio.sleep(delay)
            if not _is_local_active():
                return
            state = _stream_health_state()
            if state == "healthy":
                self.coordinator.record_stream_success(cam_id)
                return
            if state == "no_consumer":
                # No HLS consumer asked for the stream — FFmpeg never started,
                # so there's nothing to restart. Leaving the LOCAL session up
                # so a future consumer (browser tab opens) gets it instantly.
                _LOGGER.debug(
                    "Stream health watchdog: %s LOCAL session up but no HLS "
                    "consumer connected — skipping health check (frontend "
                    "card may be unmounted)",
                    cam_id[:8],
                )
                return
            # On the second consecutive failure (~2 min with no healthy
            # output), escalate: saturate the error counter so the next
            # try_live_connection() is forced to REMOTE regardless of the
            # per-model threshold. Single failure still follows the normal
            # gradual-escalation path via record_stream_error().
            is_final = idx == 1
            if is_final:
                cfg = self.coordinator.get_model_config(cam_id)
                self.coordinator.stream_error_count[cam_id] = cfg.max_stream_errors
                _LOGGER.warning(
                    "Stream health watchdog: %s LOCAL stream still not healthy "
                    "after ~2 min — forcing REMOTE fallback",
                    cam_id[:8],
                )
            else:
                self.coordinator.record_stream_error(cam_id)
                _LOGGER.warning(
                    "Stream health watchdog: %s LOCAL stream not healthy at %ds — "
                    "recording error and restarting",
                    cam_id[:8],
                    delay,
                )
            self.coordinator.live_connections.pop(cam_id, None)
            await self.coordinator.stop_tls_proxy(cam_id)
            # Re-check user intent after the 60s sleep + tear-down: user
            # may have toggled the switch OFF in the meantime, in which
            # case `_tear_down_live_stream` already cleared the intent.
            # Without this guard the watchdog re-opens the stream against
            # the user's wishes. Bug 2026-05-20.
            if cam_id not in self.coordinator.user_intent_streams:
                _LOGGER.debug(
                    "Stream health watchdog: %s — user intent gone, skipping reconnect",
                    cam_id[:8],
                )
                return
            result = await self.coordinator.try_live_connection(cam_id)
            if result:
                _LOGGER.info(
                    "Stream health watchdog: %s restarted as %s",
                    cam_id[:8],
                    result.get("_connection_type", "?"),
                )
                # If we fell back to REMOTE, stop watching — REMOTE has no
                # pre-warm dependency and no LOCAL-specific failure modes.
                if result.get("_connection_type") != "LOCAL":
                    self.async_write_ha_state()
                    return
            self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Clear the live session and stop the TLS proxy."""
        self._last_stream_off = time.monotonic()
        _LOGGER.info("Live stream OFF for %s", self._cam_title)
        # Drop user intent first — health watchdog scheduled by the
        # previous turn_on may still be sleeping and must see the cleared
        # intent when it wakes up (Bug 2026-05-20: watchdog re-opened
        # stream after user OFF if the OFF landed mid-sleep).
        self.coordinator.user_intent_streams.discard(self._cam_id)
        # Shared teardown: cancels renewal task, pops _live_connections,
        # stops TLS proxy + go2rtc, stops HA's camera.stream so
        # stream_worker can't auto-restart against the dead proxy.
        await self.coordinator.tear_down_live_stream(self._cam_id)
        # Update state immediately so the UI reflects OFF without waiting
        # for the coordinator refresh that follows.
        self.async_write_ha_state()
        self.hass.async_create_task(self.coordinator.async_request_refresh())


# ─────────────────────────────────────────────────────────────────────────────
class BoschAudioSwitch(_BoschSwitchBase, RestoreEntity):
    """Switch: ON = live audio plays, OFF = muted. Synced across every session.

    The live stream ALWAYS carries the AAC track now (≈ negligible bandwidth), so
    this is a lightweight, automatable MUTE preference that the Lovelace card
    applies to its <video> element (video.muted). Toggling it does NOT re-open the
    stream and HA pushes the change to every open card, so mute/unmute is instant
    and consistent across devices. Paired with number.<cam>_audio_volume (volume).

    This switch is the SINGLE source of truth for mute/unmute: its state persists
    across restarts via RestoreEntity, so a user's choice always wins over any
    implicit default (the card re-reads it on every stream start). There is no
    forced default-on — a brand-new camera that has never been toggled starts
    muted (OFF, no unexpected audio); the user's first toggle then sticks forever.
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_audio_{cam_id.lower()}"
        self._attr_translation_key = "audio"
        self._attr_entity_category = EntityCategory.CONFIG
        # First-install seed: muted. The persisted state (restored in
        # async_added_to_hass) overrides this for any camera the user has toggled.
        coordinator.audio_enabled.setdefault(cam_id, False)

    @property
    @override
    def is_on(self) -> bool:
        return self.coordinator.audio_enabled.get(self._cam_id, False)

    @override
    async def async_added_to_hass(self) -> None:
        # Restore the user's last mute/unmute choice so the switch survives
        # restarts and remains the authoritative state (no default-on reset).
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in ("on", "off"):
            self.coordinator.audio_enabled[self._cam_id] = last.state == "on"
            _LOGGER.debug(
                "audio: restored %s for %s from previous state",
                last.state,
                self._cam_id[:8],
            )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Unmute — the card applies it to video.muted; no stream re-open."""
        _LOGGER.info("Audio ON (unmute) for %s", self._cam_title)
        self.coordinator.audio_enabled[self._cam_id] = True
        # is_on reads the _audio_enabled dict, so write state immediately for an
        # instant, non-stale toggle that HA then pushes to every card (#22).
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Mute — the card applies it to video.muted; no stream re-open."""
        _LOGGER.info("Audio OFF (mute) for %s", self._cam_title)
        self.coordinator.audio_enabled[self._cam_id] = False
        self.async_write_ha_state()


# ─────────────────────────────────────────────────────────────────────────────
class BoschCameraLightSwitch(_BoschSwitchBase):
    """Switch: ON = camera indicator LED on, OFF = LED off.

    Only registered for cameras with featureSupport.light = True (from cloud API).
    State is read from cloud API featureStatus (frontIlluminatorInGeneralLightOn).
    Write (turn on/off) uses Bosch cloud API: PUT /v11/video_inputs/{id}/lighting_override.
    No SHC local API needed — works without SHC configured.
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_light_{cam_id.lower()}"
        self._attr_translation_key = "camera_light"

    @property
    @override
    def is_on(self) -> bool | None:
        return self.coordinator.shc_state_cache.get(
            self._cam_id, {}
        ).get(  # value is correct at runtime; HA/external source is Any-typed
            "camera_light"
        )

    @property
    @override
    def available(self) -> bool:
        """Available when coordinator is running, camera online, and light support present.

        Control uses cloud API (PUT /v11/video_inputs/{id}/lighting_override).
        Requires camera ONLINE: light control needs camera to respond.
        """
        return (
            self.coordinator.last_update_success
            and self.coordinator.is_camera_online(self._cam_id)
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        success = await self.coordinator.async_cloud_set_camera_light(
            self._cam_id, True
        )
        if not success:
            self._warn_write_failed("Camera light", "ON")

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        success = await self.coordinator.async_cloud_set_camera_light(
            self._cam_id, False
        )
        if not success:
            self._warn_write_failed("Camera light", "OFF")


# ─────────────────────────────────────────────────────────────────────────────
class BoschFrontLightSwitch(_BoschSwitchBase):
    """Switch: front spotlight on/off (independent of wallwasher).

    Uses cloud API: PUT /v11/video_inputs/{id}/lighting_override
    Only registered for cameras with featureSupport.light = True.
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_front_light_{cam_id.lower()}"
        self._attr_translation_key = "front_light"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def is_on(self) -> bool | None:
        return self.coordinator.shc_state_cache.get(
            self._cam_id, {}
        ).get(  # value is correct at runtime; HA/external source is Any-typed
            "front_light"
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        success = await self.coordinator.async_cloud_set_light_component(
            self._cam_id, "front", True
        )
        if not success:
            self._warn_write_failed("Front light", "ON")

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        success = await self.coordinator.async_cloud_set_light_component(
            self._cam_id, "front", False
        )
        if not success:
            self._warn_write_failed("Front light", "OFF")


# ─────────────────────────────────────────────────────────────────────────────
class BoschWallwasherSwitch(_BoschSwitchBase):
    """Switch: top + bottom ambient lights on/off (independent of front light).

    Gen1: Uses cloud API: PUT /v11/video_inputs/{id}/lighting_override (wallwasherOn)
    Gen2: Uses cloud API: PUT /v11/video_inputs/{id}/lighting/switch/topdown (enabled)
    Only registered for cameras with featureSupport.light = True.
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_wallwasher_{cam_id.lower()}"
        self._attr_translation_key = "wallwasher"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def is_on(self) -> bool | None:
        return self.coordinator.shc_state_cache.get(self._cam_id, {}).get("wallwasher")

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        success = await self.coordinator.async_cloud_set_light_component(
            self._cam_id, "wallwasher", True
        )
        if not success:
            self._warn_write_failed("Wallwasher", "ON")

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        success = await self.coordinator.async_cloud_set_light_component(
            self._cam_id, "wallwasher", False
        )
        if not success:
            self._warn_write_failed("Wallwasher", "OFF")


# ─────────────────────────────────────────────────────────────────────────────
class BoschPrivacyModeSwitch(_BoschSwitchBase):
    """Switch: ON = privacy mode active (camera off / shutter closed), OFF = camera active.

    Uses the Bosch cloud API: PUT /v11/video_inputs/{id}/privacy
    No SHC local API required — works without SHC configured.
    State is read from the /v11/video_inputs response (privacyMode field).
    Falls back to SHC API if cloud call fails and SHC is configured.
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_privacy_{cam_id.lower()}"
        self._attr_translation_key = "privacy_mode"
        # Debounce/coalesce state: a toggle that arrives during the cooldown /
        # warm-up window is remembered here (latest wins) and applied once the
        # window clears — instead of raising into the caller (which aborted an
        # automation's remaining steps, live ERROR 2026-06-10).
        self._pending_privacy: bool | None = None
        self._pending_apply_task: asyncio.Task[None] | None = None

    @property
    @override
    def is_on(self) -> bool | None:
        """True when privacy mode is ON (camera blocked/shuttered).

        Read from cloud API response (privacyMode field in /v11/video_inputs).
        Available immediately without SHC configured. While a toggle is deferred
        (cooldown/warm-up), reflect the pending (intended) state so the card's
        optimistic flip stays correct until the write lands — no snap-back.
        """
        if self._pending_privacy is not None:
            return self._pending_privacy
        return self.coordinator.shc_state_cache.get(
            self._cam_id, {}
        ).get(  # value is correct at runtime; HA/external source is Any-typed
            "privacy_mode"
        )

    @property
    @override
    def available(self) -> bool:
        """Available whenever a write would actually go through.

        Three viable paths:
          1. Cloud healthy and we have a known privacy state → primary path.
          2. Cloud unhealthy BUT camera is LAN-reachable AND Gen2 → the
             coordinator's `async_cloud_set_privacy_mode` already falls back
             to `rcp_local_write_privacy` which talks directly to the camera
             on port 443 without any Bosch infrastructure. Works even on a
             cold start when the in-memory cache is empty — `is_on` returns
             `None` (HA renders "unknown"), but the user can still toggle.
          3. We are inside the post-write grace window — the camera has not
             completed its cred-rotation reboot yet but a fresh write would
             still queue and succeed once the session re-opens.

        Without (2) the switch goes grey for the duration of every Bosch
        cloud 5xx burst, even though the user can still toggle privacy via
        the official app on the same LAN. The pre-v12.4.10 "must have
        cached state" gate caused that grey-out after every HA restart that
        landed during a cloud outage — fixed below by letting LAN
        reachability stand on its own merits.

        Exception: during firmware install the camera reboots — neither
        cloud nor LAN path will accept writes for several minutes. Flip
        unavailable until the slow-tier poll clears the `updating` flag.
        """
        is_updating = getattr(self.coordinator, "is_updating", None)
        if is_updating is not None and is_updating(self._cam_id):
            return False
        cache = self.coordinator.shc_state_cache.get(self._cam_id, {})
        has_cached_state = cache.get("privacy_mode") is not None
        if self.coordinator.last_update_success and has_cached_state:
            return True
        # Cloud unhealthy — fall back to LAN reachability for Gen2 cams.
        # Intentionally does NOT require cached state: a cold start during
        # cloud-503 leaves the cache empty, but the LAN RCP write path
        # still succeeds. `is_on` will return None until the next live
        # state is observed, HA renders that as "unknown", toggles work.
        is_lan_reachable = getattr(self.coordinator, "is_lan_reachable", None)
        if is_lan_reachable is None:
            return False
        if not bool(is_lan_reachable(self._cam_id)):
            return False
        # Gate the LAN fallback to cams that actually have a working LAN
        # RCP write surface. Gen2 known: yes. Gen1 known: no (no local
        # rcp.xml endpoint). Hardware-version unknown (cold start during
        # cloud outage, _hw_version cache empty + device-registry stale):
        # let the user try — the write either succeeds (Gen2) or fails
        # cleanly (Gen1, no LAN endpoint), and not gating means the user
        # can recover privacy/light on a Gen2 cam during a multi-hour
        # cloud outage without waiting for hw_version to backfill.
        # Bug 2026-05-20 (Bosch maintenance window, hw_version never
        # populated on Indoor II → switch grey, user stuck).
        if _is_gen2(self.coordinator, self._cam_id):
            return True
        hw = self.coordinator.hw_version.get(self._cam_id)
        if hw in (None, "", "CAMERA"):
            # Hardware version not yet known — allow the toggle, the LAN
            # write will short-circuit for Gen1 (no rcp.xml endpoint).
            return True
        return False

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Extra attributes including RCP-sourced privacy state for cross-validation.

        rcp_state: privacy mask byte[1] from RCP command 0x0d00 (1=ON, 0=OFF, None=unavailable).
        This supplements the REST API privacy state with a direct camera-side reading.
        The switch logic (is_on) remains driven by the REST API only.
        """
        rcp_raw = self.coordinator.rcp_privacy_cache.get(self._cam_id)
        return {
            "rcp_state": rcp_raw,
        }

    # Minimum seconds between privacy mode changes per camera.
    # Rapid toggling can stress the camera firmware (red LED / reboot).
    _PRIVACY_COOLDOWN = 5
    # When a toggle arrives during the cooldown / warm-up, the desired state is
    # deferred and re-checked this often, giving up after the cap (warm-up can
    # take ~30 s; the cap guards against a stuck `is_stream_warming`).
    _PRIVACY_PENDING_POLL = 1.0
    _PRIVACY_PENDING_MAX_WAIT = 90.0

    def _check_cooldown(self) -> bool:
        """Return True if cooldown period has passed, False if too soon."""
        # Block during stream warm-up (TLS proxy + encoder init)
        if self.coordinator.is_stream_warming(self._cam_id):
            _LOGGER.warning(
                "Privacy toggle for %s blocked — stream is warming up",
                self._cam_title,
            )
            return False
        # Block rapid toggles
        # SENTINEL_RULE: "never set" must be float("-inf"), never 0 — on a freshly
        # booted host time.monotonic() can be < _PRIVACY_COOLDOWN, and a 0 default
        # would make `monotonic() - 0` look like a recent toggle and falsely block
        # the very first privacy change (the stream cooldown guards this with
        # `last_off > 0`; this path had no such guard).
        last = self.coordinator.privacy_set_at.get(self._cam_id, float("-inf"))
        elapsed = time.monotonic() - last
        if elapsed < self._PRIVACY_COOLDOWN:
            remaining = self._PRIVACY_COOLDOWN - elapsed
            _LOGGER.warning(
                "Privacy toggle for %s blocked — cooldown %.0fs remaining (prevents camera stress)",
                self._cam_title,
                remaining,
            )
            return False
        return True

    def _cooldown_message(self) -> str:
        """Human-facing reason the privacy toggle is currently blocked.

        Raised to the caller (and surfaced by the Lovelace card's rollback) so a
        rejected toggle is never silently swallowed — which previously left the
        card optimistically flipped to the wrong state for 8 s and made the
        button look like it had hung (RkcCorian, #27).
        """
        if self.coordinator.is_stream_warming(self._cam_id):
            return (
                f"Cannot toggle privacy for {self._cam_title} yet — the live "
                "stream is still starting. Try again in a few seconds."
            )
        # SENTINEL_RULE: "never set" must be float("-inf"), never 0 — on a freshly
        # booted host time.monotonic() can be < _PRIVACY_COOLDOWN, and a 0 default
        # would make `monotonic() - 0` look like a recent toggle and falsely block
        # the very first privacy change (the stream cooldown guards this with
        # `last_off > 0`; this path had no such guard).
        last = self.coordinator.privacy_set_at.get(self._cam_id, float("-inf"))
        remaining = max(1, round(self._PRIVACY_COOLDOWN - (time.monotonic() - last)))
        return (
            f"Privacy for {self._cam_title} was just changed — please wait "
            f"{remaining}s before toggling again (protects the camera from "
            "rapid switching)."
        )

    def _privacy_block_remaining(self) -> float:
        """Seconds to wait before a privacy write is allowed (0.0 = now).

        Returns the poll interval while the stream is still warming up (its end
        is not known up front) and the exact remaining cooldown after a recent
        toggle. Silent counterpart to `_check_cooldown` for the deferred loop.
        """
        if self.coordinator.is_stream_warming(self._cam_id):
            return self._PRIVACY_PENDING_POLL
        # SENTINEL_RULE: "never set" is float("-inf"), never 0.
        last = self.coordinator.privacy_set_at.get(self._cam_id, float("-inf"))
        remaining = self._PRIVACY_COOLDOWN - (time.monotonic() - last)
        return remaining if remaining > 0 else 0.0

    async def _apply_privacy(self, desired: bool) -> None:
        """Perform the actual privacy write (and stop the stream when enabling).

        Stops any active live stream on enable — the camera can't stream while
        the shutter is closed; the shared teardown cancels the renewal task and
        stops HA's camera.stream so the worker doesn't auto-restart against the
        now-dead TLS proxy (HTTP 443 privacy-gated).
        """
        if desired and self._cam_id in self.coordinator.live_connections:
            _LOGGER.info(
                "Privacy ON for %s — stopping active live stream", self._cam_title
            )
            await self.coordinator.tear_down_live_stream(self._cam_id)
        success = await self.coordinator.async_cloud_set_privacy_mode(
            self._cam_id, desired
        )
        if not success:
            # The cascade (cloud → Gen2 LOCAL RCP → SHC) never raises — an
            # automation calling this must keep running its later steps
            # (see _request_privacy). But that means a total failure is
            # otherwise silent to whoever pressed the switch: `is_on` still
            # reflects the last cached state, so the UI just reverts with
            # zero explanation. Log it here so it's at least visible without
            # digging through shc.py's persistent_notification.
            _LOGGER.warning(
                "Privacy toggle for %s (%s) failed on all paths "
                "(cloud+local RCP+SHC) — state unchanged",
                self._cam_title,
                "ON" if desired else "OFF",
            )

    async def _flush_pending_privacy(self) -> None:
        """Apply whatever the latest pending desired state is, then clear it."""
        desired = self._pending_privacy
        self._pending_privacy = None
        if desired is not None:
            await self._apply_privacy(desired)

    async def _pending_privacy_loop(self) -> None:
        """Wait out the cooldown / warm-up, then apply the latest pending state.

        Coalescing: `_pending_privacy` is overwritten by later toggles, so the
        most recent intent wins. Never raises into a service caller.
        """
        waited = 0.0
        try:
            while waited < self._PRIVACY_PENDING_MAX_WAIT:
                remaining = self._privacy_block_remaining()
                if remaining <= 0:
                    break
                delay = min(remaining, self._PRIVACY_PENDING_POLL)
                await asyncio.sleep(delay)
                waited += delay
            else:
                _LOGGER.warning(
                    "Privacy toggle for %s still blocked after %.0fs — applying now",
                    self._cam_title,
                    waited,
                )
            await self._flush_pending_privacy()
        except asyncio.CancelledError:
            raise
        except Exception as err:
            # Deferred best-effort apply — surface the failure, don't crash the
            # background loop task.
            _LOGGER.warning(
                "Privacy deferred apply for %s failed: %s", self._cam_title, err
            )
        finally:
            self._pending_apply_task = None
            self.async_write_ha_state()

    async def _request_privacy(self, desired: bool) -> None:
        """Set privacy to `desired`, debouncing/coalescing during cooldown.

        Apply immediately when allowed; otherwise remember the latest desired
        state and apply it once the cooldown / warm-up clears. NEVER raises —
        an automation calling this must keep running its later steps (a raised
        ServiceValidationError previously aborted the whole action sequence,
        live ERROR 2026-06-10). The card's optimistic flip stays correct because
        `is_on` reflects the pending state until the write lands.
        """
        self._pending_privacy = desired
        if self._privacy_block_remaining() <= 0:
            await self._flush_pending_privacy()
            return
        _LOGGER.debug(
            "Privacy toggle for %s deferred — applying %s once cooldown/warm-up clears",
            self._cam_title,
            "ON" if desired else "OFF",
        )
        self.async_write_ha_state()  # reflect the intended state immediately
        if self._pending_apply_task is None or self._pending_apply_task.done():
            self._pending_apply_task = self.hass.async_create_task(
                self._pending_privacy_loop(),
                name=f"bosch_privacy_pending_{self._cam_id[:8]}",
            )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable privacy mode — camera turns off / shutter closes."""
        await self._request_privacy(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable privacy mode — camera turns back on."""
        await self._request_privacy(False)

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel a pending deferred-apply task on entity removal/reload."""
        task = self._pending_apply_task
        if task is not None and not task.done():
            task.cancel()
        await super().async_will_remove_from_hass()


# ─────────────────────────────────────────────────────────────────────────────
class BoschNotificationsSwitch(_BoschSwitchBase):
    """Switch: ON = notifications enabled (FOLLOW_CAMERA_SCHEDULE or ON_CAMERA_SCHEDULE), OFF = ALWAYS_OFF.

    Three-state aware: the API can return FOLLOW_CAMERA_SCHEDULE, ON_CAMERA_SCHEDULE, or ALWAYS_OFF.
    Both "ON" variants are treated as switch state = True.
    Turning ON always sends FOLLOW_CAMERA_SCHEDULE.

    Uses Bosch cloud API: PUT /v11/video_inputs/{id}/enable_notifications.
    State is read from the /v11/video_inputs response (notificationsEnabledStatus field).
    No SHC local API required.
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_notifications_{cam_id.lower()}"
        self._attr_translation_key = "notifications"
        self._attr_entity_category = EntityCategory.CONFIG

    # Values that map to ON state (notifications active in some form)
    _NOTIFICATIONS_ON_STATES: ClassVar[set[str]] = {
        "FOLLOW_CAMERA_SCHEDULE",
        "ON_CAMERA_SCHEDULE",
    }

    @property
    @override
    def is_on(self) -> bool | None:
        status = self.coordinator.shc_state_cache.get(self._cam_id, {}).get(
            "notifications_status"
        )
        if status is None:
            return None
        return status in self._NOTIFICATIONS_ON_STATES

    @property
    @override
    def available(self) -> bool:
        """Cloud-only: available without camera being ONLINE.

        Notification state comes from the cloud API — overrides base class
        is_camera_online() guard intentionally.
        """
        return (
            self.coordinator.last_update_success
            and self.coordinator.shc_state_cache.get(self._cam_id, {}).get(
                "notifications_status"
            )
            is not None
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable notifications (follow camera schedule)."""
        success = await self.coordinator.async_cloud_set_notifications(
            self._cam_id, True
        )
        if not success:
            self._warn_write_failed("Notifications", "ON")

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable notifications (always off)."""
        success = await self.coordinator.async_cloud_set_notifications(
            self._cam_id, False
        )
        if not success:
            self._warn_write_failed("Notifications", "OFF")


# ─────────────────────────────────────────────────────────────────────────────
class BoschMotionEnabledSwitch(_BoschSwitchBase):
    """Toggle motion detection on/off.

    KNOWN LIMITATION: The camera firmware has an internal IVA rules engine that
    enforces motion detection settings independently. Changes via this switch
    (cloud API PUT /motion) are accepted but may be reverted within ~1 second
    by the camera's on-device automation rules. Settings controlled via the SHC
    (privacy mode, camera light) are NOT affected by this issue.
    See: GET /v11/video_inputs/{id}/rules (returns [] — rules stored on-device).
    """

    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "motion_detection"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_motion_enabled"

    @property
    @override
    def is_on(self) -> bool | None:
        settings = self.coordinator.motion_settings(self._cam_id)
        if not settings:
            return None
        return settings.get("enabled", False)  # type: ignore[no-any-return]

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        if _is_gen2_indoor(self) and await _warn_if_privacy_on(
            self, "Motion Detection"
        ):
            return
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
    async def async_turn_off(self, **kwargs: Any) -> None:
        if _is_gen2_indoor(self) and await _warn_if_privacy_on(
            self, "Motion Detection"
        ):
            return
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


# ─────────────────────────────────────────────────────────────────────────────
class BoschRecordSoundSwitch(_BoschSwitchBase):
    """Toggle audio in cloud event recordings."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "record_sound"

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_record_sound"

    @property
    @override
    def is_on(self) -> bool | None:
        opts = self.coordinator.recording_options(self._cam_id)
        if not opts:
            return None
        return opts.get("recordSound", False)  # type: ignore[no-any-return]

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_put_camera(
            self._cam_id, "recording_options", {"recordSound": True}
        )
        self.hass.async_create_task(self.coordinator.async_request_refresh())

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_put_camera(
            self._cam_id, "recording_options", {"recordSound": False}
        )
        self.hass.async_create_task(self.coordinator.async_request_refresh())


# ─────────────────────────────────────────────────────────────────────────────
class BoschAutoFollowSwitch(_BoschSwitchBase):
    """Toggle auto-follow (camera automatically pans to track motion).

    Only available on CAMERA_360 (indoor) — cameras with panLimit > 0.
    Uses cloud API: GET/PUT /v11/video_inputs/{id}/autofollow
    Body: {"result": true/false}
    Response: HTTP 204 on success.
    """

    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "auto_follow"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_autofollow"

    @property
    @override
    def is_on(self) -> bool | None:
        data = self.coordinator.data.get(self._cam_id, {}).get("autofollow")
        if data is None:
            return None
        return data.get("result", False)  # type: ignore[no-any-return]

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.async_put_camera(
            self._cam_id, "autofollow", {"result": True}
        )
        self.hass.async_create_task(self.coordinator.async_request_refresh())

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.async_put_camera(
            self._cam_id, "autofollow", {"result": False}
        )
        self.hass.async_create_task(self.coordinator.async_request_refresh())


# ─────────────────────────────────────────────────────────────────────────────
class BoschIntercomSwitch(_BoschSwitchBase, RestoreEntity):
    """Switch: ON = intercom (two-way audio) active, OFF = intercom off.

    When turned ON: enables speaker via PUT /v11/video_inputs/{id}/audio
    with {"audioEnabled": True, "speakerLevel": 50} merged onto the current
    cached body (preserves microphoneLevel — capture 2026-04-08 confirms the
    body shape {"audioEnabled":true,"microphoneLevel":60,"speakerLevel":80}).
    When turned OFF: disables speaker with {"audioEnabled": False}, same
    merge. Shares coordinator.audio_cache and a per-camera lock with
    BoschSpeakerLevelNumber/BoschMicrophoneLevelNumber (same endpoint) so a
    concurrent write to a sibling field can't be clobbered by a stale
    snapshot.

    Bug-hunt 2026-07-03: previously used a raw session.put (no 401/token-
    refresh retry, unlike async_put_camera), sent the wrong JSON key casing
    ("SpeakerLevel" instead of the API's "speakerLevel" — silently ignored
    by the API, so speaker level 50 was never actually applied), omitted
    microphoneLevel entirely from the ON body, and never wrote back to
    _audio_cache — leaving the Speaker/Microphone Number entities' cached
    view permanently stale after every intercom toggle.
    Disabled by default — enable in Settings -> Entities.
    """

    _attr_translation_key = "intercom"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_intercom"
        self._is_on: bool = False

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the intercom ON/OFF state from the last HA session."""
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state in ("on", "off"):
            self._is_on = last.state == "on"
            _LOGGER.debug(
                "intercom: restored %s for %s from previous state",
                last.state,
                self._cam_id[:8],
            )

    @property
    @override
    def is_on(self) -> bool:
        return self._is_on

    async def _async_set_intercom(self, *, enabled: bool) -> None:
        """Read-modify-write the shared /audio body under the shared lock."""
        lock = _get_cam_lock(self.coordinator, "_audio_config_locks", self._cam_id)
        async with lock:
            audio = dict(self.coordinator.audio_cache.get(self._cam_id, {}))
            audio["audioEnabled"] = enabled
            if enabled:
                audio["speakerLevel"] = 50
            success = await self.coordinator.async_put_camera(
                self._cam_id, "audio", audio
            )
            if success:
                self._is_on = enabled
                cache = self.coordinator.audio_cache.setdefault(self._cam_id, {})
                cache["audioEnabled"] = enabled
                if enabled:
                    cache["speakerLevel"] = 50
                _LOGGER.info(
                    "Intercom %s for %s", "ON" if enabled else "OFF", self._cam_title
                )
            else:
                _LOGGER.warning(
                    "Intercom %s failed for %s: HTTP error",
                    "ON" if enabled else "OFF",
                    self._cam_title,
                )
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable intercom (two-way audio) with speaker level 50."""
        await self._async_set_intercom(enabled=True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable intercom (two-way audio)."""
        await self._async_set_intercom(enabled=False)


# ─────────────────────────────────────────────────────────────────────────────
class BoschPrivacySoundSwitch(_BoschSwitchBase):
    """Switch: ON = privacy sound override active, OFF = privacy sound off.

    Maps to the iOS app "Ton" toggle under Kamera-Funktionen — when enabled,
    the camera plays an audible tone when privacy mode changes.
    Uses cloud API: GET/PUT /v11/video_inputs/{id}/privacy_sound_override
    Body: {"result": true/false}
    Supported: CAMERA_360 (Gen1 Indoor), HOME_Eyes_Indoor (Gen2 Indoor II).
    Outdoor cameras return 442.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "privacy_sound"

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_privacy_sound"

    @property
    @override
    def is_on(self) -> bool | None:
        return self.coordinator.privacy_sound_cache.get(self._cam_id)

    @property
    @override
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.is_camera_online(self._cam_id)
            and self.coordinator.privacy_sound_cache.get(self._cam_id) is not None
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_apply_toggle(
            "privacy_sound_override",
            {"result": True},
            self.coordinator.privacy_sound_cache,
            self.coordinator.privacy_sound_set_at,
            True,
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_apply_toggle(
            "privacy_sound_override",
            {"result": False},
            self.coordinator.privacy_sound_cache,
            self.coordinator.privacy_sound_set_at,
            False,
        )


# ─────────────────────────────────────────────────────────────────────────────
class BoschTimestampSwitch(_BoschSwitchBase):
    """Switch: ON = time/date overlay visible on video, OFF = hidden.

    Uses cloud API: GET/PUT /v11/video_inputs/{id}/timestamp
    Body: {"result": true/false}
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "timestamp_overlay"

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_timestamp"

    @property
    @override
    def is_on(self) -> bool | None:
        return self.coordinator.timestamp_cache.get(self._cam_id)

    @property
    @override
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.is_camera_online(self._cam_id)
            and self.coordinator.timestamp_cache.get(self._cam_id) is not None
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_apply_toggle(
            "timestamp",
            {"result": True},
            self.coordinator.timestamp_cache,
            self.coordinator.timestamp_set_at,
            True,
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_apply_toggle(
            "timestamp",
            {"result": False},
            self.coordinator.timestamp_cache,
            self.coordinator.timestamp_set_at,
            False,
        )


# ─────────────────────────────────────────────────────────────────────────────
class BoschStatusLedSwitch(_BoschSwitchBase):
    """Switch: status LED on/off (Gen2 cameras only).

    Uses cloud API: GET/PUT /v11/video_inputs/{id}/ledlights
    Body: {"state": "ON"/"OFF"}
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "status_led"

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_ledlights"

    @property
    @override
    def is_on(self) -> bool | None:
        return self.coordinator.ledlights_cache.get(self._cam_id)

    @property
    @override
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.is_camera_online(self._cam_id)
            and self.coordinator.ledlights_cache.get(self._cam_id) is not None
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._async_apply_toggle(
            "ledlights",
            {"state": "ON"},
            self.coordinator.ledlights_cache,
            self.coordinator.ledlights_set_at,
            True,
        )

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._async_apply_toggle(
            "ledlights",
            {"state": "OFF"},
            self.coordinator.ledlights_cache,
            self.coordinator.ledlights_set_at,
            False,
        )


# ─────────────────────────────────────────────────────────────────────────────
class BoschMotionLightSwitch(_BoschSwitchBase):
    """Switch: motion-triggered lighting on/off (Gen2 only).

    When ON, camera lights turn on automatically when motion is detected.
    Uses cloud API: GET/PUT /v11/video_inputs/{id}/lighting/motion
    Toggles lightOnMotionEnabled field, preserves all other settings.
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_motion_light"
        self._attr_translation_key = "motion_light"
        self._attr_entity_category = EntityCategory.CONFIG
        self._is_on: bool | None = None

    @property
    @override
    def is_on(self) -> bool | None:
        # The coordinator re-polls lighting/motion on the slow tier, so the cache
        # is the source of truth and reflects changes made in the Bosch app. Read
        # it fresh each time; _is_on is only the optimistic value before the cache
        # has ever been filled (else a frozen _is_on hid external changes forever).
        cache = self.coordinator.motion_light_cache.get(self._cam_id, {})
        if cache:
            return bool(cache.get("lightOnMotionEnabled", False))
        return self._is_on

    @property
    @override
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.is_camera_online(self._cam_id)
        )

    async def _set_motion_light(self, enabled: bool) -> None:
        """Read current motion light config, toggle enabled, write back."""
        # Read current config from cache or API
        cache = self.coordinator.motion_light_cache.get(self._cam_id, {})
        if not cache:
            # Fetch fresh if cache empty
            token = self.coordinator.token
            if not token:
                return
            session = await async_get_bosch_cloud_session(self.hass)
            try:
                async with asyncio.timeout(10):
                    async with session.get(
                        f"https://residential.cbs.boschsecurity.com/v11/video_inputs/{self._cam_id}/lighting/motion",
                        headers={"Authorization": f"Bearer {token}"},
                    ) as resp:
                        if resp.status == 200:
                            cache = await resp.json()
                        else:
                            _LOGGER.warning(
                                "Motion light GET HTTP %d for %s",
                                resp.status,
                                self._cam_id[:8],
                            )
                            return
            except Exception:
                _LOGGER.exception("Motion light GET error for %s", self._cam_id[:8])
                return
        # Update the enabled flag and write back
        data = dict(cache)
        data["lightOnMotionEnabled"] = enabled
        success = await self.coordinator.async_put_camera(
            self._cam_id, "lighting/motion", data
        )
        if success:
            self._is_on = enabled
            self.coordinator.motion_light_cache[self._cam_id] = data
            _LOGGER.info(
                "Motion light %s for %s", "ON" if enabled else "OFF", self._cam_id[:8]
            )
        else:
            _LOGGER.warning("Motion light PUT failed for %s", self._cam_id[:8])
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_motion_light(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_motion_light(False)


# ─────────────────────────────────────────────────────────────────────────────
class BoschAmbientLightSwitch(_BoschSwitchBase):
    """Switch: ambient/permanent lighting on/off (Gen2 only).

    When ON, camera lights stay on according to schedule (dusk-to-dawn or manual times).
    Uses cloud API: GET/PUT /v11/video_inputs/{id}/lighting/ambient
    Toggles ambientLightEnabled field, preserves schedule and brightness settings.
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_ambient_light"
        self._attr_translation_key = "ambient_light"
        self._attr_entity_category = EntityCategory.CONFIG
        self._is_on: bool | None = None

    @property
    @override
    def is_on(self) -> bool | None:
        # Cache is the source of truth (slow-tier re-poll reflects Bosch-app
        # changes); _is_on is only the optimistic pre-cache fallback.
        cache = self.coordinator.ambient_lighting_cache.get(self._cam_id, {})
        if cache:
            return bool(cache.get("ambientLightEnabled", False))
        return self._is_on

    @property
    @override
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.is_camera_online(self._cam_id)
        )

    async def _set_ambient_light(self, enabled: bool) -> None:
        token = self.coordinator.token
        if not token:
            return
        session = await async_get_bosch_cloud_session(self.hass)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        url = f"https://residential.cbs.boschsecurity.com/v11/video_inputs/{self._cam_id}/lighting/ambient"
        try:
            async with asyncio.timeout(10):
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        return
                    data = await resp.json()
            data["ambientLightEnabled"] = enabled
            async with asyncio.timeout(10):
                async with session.put(url, headers=headers, json=data) as resp:
                    if resp.status in (200, 201, 204):
                        self._is_on = enabled
                        self.coordinator.ambient_lighting_cache[self._cam_id] = data
        except Exception:
            _LOGGER.exception("Ambient light error for %s", self._cam_id[:8])
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_ambient_light(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_ambient_light(False)


# ─────────────────────────────────────────────────────────────────────────────
class BoschSoftLightFadingSwitch(_BoschSwitchBase):
    """Switch: soft light fading (Gen2 only).

    When ON, lights fade smoothly instead of snapping on/off.
    Uses cloud API: GET/PUT /v11/video_inputs/{id}/lighting
    Body: {"darknessThreshold": float, "softLightFading": bool}
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "soft_light_fading"

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_soft_light_fading"

    @property
    @override
    def is_on(self) -> bool | None:
        cache = self.coordinator.global_lighting_cache.get(self._cam_id, {})
        return cache.get("softLightFading") if cache else None

    @property
    @override
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.is_camera_online(self._cam_id)
            and bool(self.coordinator.global_lighting_cache.get(self._cam_id))
        )

    async def _put_global_lighting(self, enabled: bool) -> None:
        token = self.coordinator.token
        if not token:
            return
        cache = self.coordinator.global_lighting_cache.get(self._cam_id, {})
        # Preserve existing darknessThreshold
        threshold = cache.get("darknessThreshold", 0.5)
        body = {"darknessThreshold": threshold, "softLightFading": enabled}
        session = await async_get_bosch_cloud_session(self.hass)
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        url = f"https://residential.cbs.boschsecurity.com/v11/video_inputs/{self._cam_id}/lighting"
        try:
            async with asyncio.timeout(10):
                async with session.put(url, headers=headers, json=body) as resp:
                    if resp.status in (200, 201, 204):
                        # Update cache
                        try:
                            rsp = await resp.json()
                            if isinstance(rsp, dict):
                                self.coordinator.global_lighting_cache[self._cam_id] = (
                                    rsp
                                )
                            else:
                                self.coordinator.global_lighting_cache[self._cam_id] = (
                                    body
                                )
                        except Exception:
                            self.coordinator.global_lighting_cache[self._cam_id] = body
        except Exception:
            _LOGGER.exception("Soft fading error for %s", self._cam_id[:8])
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._put_global_lighting(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._put_global_lighting(False)


# ─────────────────────────────────────────────────────────────────────────────
class BoschIntrusionDetectionSwitch(_BoschSwitchBase):
    """Switch: intrusion detection on/off (Gen2 only).

    DualRadar 180° 3D motion detection with person recognition.
    Uses cloud API: GET/PUT /v11/video_inputs/{id}/intrusionDetectionConfig
    Toggles enabled field, preserves sensitivity/detectionMode/distance.
    Extra attributes: sensitivity (1-5), detectionMode, distance (meters).
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_intrusion_detection"
        self._attr_translation_key = "intrusion_detection"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    def _config(self) -> dict[str, Any]:
        return self.coordinator.intrusion_config_cache.get(self._cam_id, {})

    @property
    @override
    def is_on(self) -> bool | None:
        return self._config.get("enabled")

    @property
    @override
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.is_camera_online(self._cam_id)
            and bool(self._config)
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "sensitivity": self._config.get("sensitivity"),
            "detection_mode": self._config.get("detectionMode"),
            "distance_meters": self._config.get("distance"),
        }

    async def _set_intrusion(self, enabled: bool) -> None:
        # Write-guard: /intrusionDetectionConfig returns HTTP 443
        # "sh:camera.in.privacy.mode" while privacy is ON. Warn the user
        # visibly instead of failing silently in the logs.
        if await _warn_if_privacy_on(self, "Intrusion Detection"):
            return
        cfg = dict(self._config)
        if not cfg:
            return
        cfg["enabled"] = enabled
        success = await self.coordinator.async_put_camera(
            self._cam_id, "intrusionDetectionConfig", cfg
        )
        if success:
            self.coordinator.intrusion_config_cache[self._cam_id] = cfg
            # Guard the next slow-tier poll (300 s) from overwriting the cache
            # with the stale cloud value while propagation is still in flight.
            self.coordinator.intrusion_config_set_at[self._cam_id] = time.monotonic()
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_intrusion(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_intrusion(False)


# ─────────────────────────────────────────────────────────────────────────────
# Audio-Plus sound analytics (Gen2): glass-break + fire/smoke alarm detection
# Cloud API: GET/PUT /v11/video_inputs/{id}/audioDetectionConfig
# Payload model: {"detectGlassBreak": bool, "detectFireAlarm": bool} — BOTH fields
# are always sent, so toggling one preserves the other. 2026-06-22.
# ─────────────────────────────────────────────────────────────────────────────
class _BoschAudioDetectionSwitchBase(_BoschSwitchBase):
    """Base for the two audioDetectionConfig toggles (glass-break / fire alarm)."""

    _attr_entity_category = EntityCategory.CONFIG
    _field: str = ""  # "detectGlassBreak" | "detectFireAlarm" (set by subclass)

    @property
    def _config(self) -> dict[str, Any]:
        return self.coordinator.audio_detection_cache.get(self._cam_id, {})

    @property
    @override
    def is_on(self) -> bool | None:
        val = self._config.get(self._field)
        return bool(val) if val is not None else None

    @property
    @override
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.is_camera_online(self._cam_id)
            and bool(self._config)
        )

    async def _set_detection(self, value: bool) -> None:
        # /audioDetectionConfig rejects writes while privacy is ON (same as the
        # other camera-config endpoints) — warn the user visibly.
        if await _warn_if_privacy_on(self, "Audio detection"):
            return
        # Serialize the read-modify-write per camera. audioDetectionConfig
        # REQUIRES both fields in every PUT, so toggling glass-break and
        # fire-alarm concurrently (a single scene targeting both switches) would
        # each build their body from a pre-toggle snapshot and re-send the OTHER
        # field's stale value — reverting it in cache AND on the camera. The lock
        # makes each write read a cache that already holds the sibling's result,
        # and we merge only our own field back (never the whole entry).
        # (bug-hunt 2026-07-01)
        locks = getattr(self.coordinator, "audio_detection_locks", None)
        if locks is None:
            locks = {}
            self.coordinator.audio_detection_locks = locks
        lock = locks.get(self._cam_id)
        if lock is None:
            lock = asyncio.Lock()
            locks[self._cam_id] = lock
        async with lock:
            # Snapshot INSIDE the lock so it reflects a sibling write that just
            # completed.
            cfg = dict(self._config)
            if not cfg:
                return
            cfg[self._field] = value
            success = await self.coordinator.async_put_camera(
                self._cam_id, "audioDetectionConfig", cfg
            )
            if success:
                # Merge only our own field into the live cache rather than
                # overwriting the whole entry, so a concurrent sibling toggle
                # isn't clobbered.
                cur = self.coordinator.audio_detection_cache.setdefault(
                    self._cam_id, {}
                )
                cur[self._field] = value
                # Guard the next slow-tier poll from reverting the optimistic
                # value while the cloud write is still propagating.
                self.coordinator.audio_detection_set_at[self._cam_id] = time.monotonic()
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_detection(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_detection(False)


class BoschGlassBreakDetectionSwitch(_BoschAudioDetectionSwitchBase):
    """Switch: glass-break sound detection (Gen2 Audio-Plus)."""

    _field = "detectGlassBreak"

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_glass_break_detection"
        self._attr_translation_key = "glass_break_detection"


class BoschFireAlarmDetectionSwitch(_BoschAudioDetectionSwitchBase):
    """Switch: smoke/fire-alarm sound detection (Gen2 Audio-Plus)."""

    _field = "detectFireAlarm"

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_fire_alarm_detection"
        self._attr_translation_key = "fire_alarm_detection"


# ─────────────────────────────────────────────────────────────────────────────
_NOTIF_TYPE_ICONS = {
    "movement": "mdi:motion-sensor",
    "person": "mdi:account-eye",
    "audio": "mdi:volume-high",
    "trouble": "mdi:alert-circle",
    "cameraAlarm": "mdi:alarm-light",
    "troubleEmail": "mdi:email-alert",
}

_NOTIF_TYPE_LABELS = {
    "movement": "Movement Notifications",
    "person": "Person Notifications",
    "audio": "Audio Notifications",
    "trouble": "Trouble Notifications (Push)",
    "cameraAlarm": "Camera Alarm Notifications",
    "troubleEmail": "Trouble Notifications (Email)",
}


class BoschNotificationTypeSwitch(_BoschSwitchBase):
    """Per-type notification toggle (movement, person, audio, trouble, cameraAlarm).

    Reads from GET /v11/video_inputs/{id}/notifications.
    Writes via PUT /v11/video_inputs/{id}/notifications with all toggles.
    """

    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: BoschCameraCoordinator,
        cam_id: str,
        entry: ConfigEntry,
        ntype: str,
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._ntype = ntype
        label = _NOTIF_TYPE_LABELS.get(ntype, ntype)
        self._attr_name = label
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_notif_{ntype}"
        # Translation keys must match [a-z0-9_-]+; convert API CamelCase → snake_case
        _tkey = ntype.replace("cameraAlarm", "camera_alarm").replace(
            "troubleEmail", "trouble_email"
        )
        self._attr_translation_key = f"notification_type_{_tkey}"

    @property
    @override
    def is_on(self) -> bool | None:
        data = self.coordinator.notifications_cache.get(self._cam_id, {})
        if not data:
            return None
        return data.get(self._ntype, False)  # type: ignore[no-any-return]

    @property
    @override
    def available(self) -> bool:
        """Cloud-only: available without camera being ONLINE.

        Notification type toggles go through the Bosch cloud API — overrides
        base class is_camera_online() guard intentionally.
        """
        return self.coordinator.last_update_success and bool(
            self.coordinator.notifications_cache.get(self._cam_id)
        )

    async def _set_type(self, value: bool) -> None:
        """Write updated notification toggles (preserving other types)."""
        current = dict(self.coordinator.notifications_cache.get(self._cam_id, {}))
        current[self._ntype] = value
        success = await self.coordinator.async_put_camera(
            self._cam_id, "notifications", current
        )
        if success:
            self.coordinator.notifications_cache[self._cam_id] = current
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_type(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_type(False)


# ─────────────────────────────────────────────────────────────────────────────
# Gen2 Indoor II — Alarm System (integrated 75 dB siren)
# ─────────────────────────────────────────────────────────────────────────────
class BoschAlarmSystemArmSwitch(_BoschSwitchBase):
    """Switch: scharf/unscharf (armed / disarmed) for the integrated alarm system.

    PUT /v11/video_inputs/{id}/intrusionSystem/arming  body: {"arm": true/false}
    State is derived from GET /v11/video_inputs/{id}/alarmStatus polling +
    optimistic update on successful PUT.
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_alarm_arm"
        self._attr_translation_key = "alarm_system_arm"

    @property
    @override
    def is_on(self) -> bool | None:
        return self.coordinator.arming_cache.get(self._cam_id)

    @property
    @override
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.is_camera_online(self._cam_id)
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self.coordinator.alarm_status_cache.get(self._cam_id, {})
        return {
            "alarm_type": status.get("alarmType"),
            "intrusion_system": status.get("intrusionSystem"),
        }

    async def _set_arm(self, arm: bool) -> None:
        await self._async_apply_toggle(
            "intrusionSystem/arming",
            {"arm": arm},
            self.coordinator.arming_cache,
            self.coordinator.arming_set_at,
            arm,
        )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_arm(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_arm(False)


class _BoschAlarmSettingsSwitchBase(_BoschSwitchBase):
    """Shared base for alarm_settings boolean toggles (alarmMode / preAlarmMode)."""

    _field: str = ""  # field to toggle (alarmMode / preAlarmMode)

    @property
    def _settings(self) -> dict[str, Any]:
        return self.coordinator.alarm_settings_cache.get(self._cam_id, {})

    @property
    @override
    def is_on(self) -> bool | None:
        val = self._settings.get(self._field)
        if val is None:
            return None
        return str(val).upper() == "ON"

    @property
    @override
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and self.coordinator.is_camera_online(self._cam_id)
            and bool(self._settings)
        )

    async def _set(self, enabled: bool) -> None:
        cfg = dict(self._settings)
        if not cfg:
            return
        cfg[self._field] = "ON" if enabled else "OFF"
        success = await self.coordinator.async_put_camera(
            self._cam_id, "alarm_settings", cfg
        )
        if success:
            self.coordinator.alarm_settings_cache[self._cam_id] = cfg
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)


class BoschAlarmModeSwitch(_BoschAlarmSettingsSwitchBase):
    """Switch: main alarm (75 dB siren) ON/OFF — alarm_settings.alarmMode."""

    _field = "alarmMode"

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_alarm_mode"
        self._attr_translation_key = "alarm_mode"
        self._attr_entity_category = EntityCategory.CONFIG


class BoschPreAlarmSwitch(_BoschAlarmSettingsSwitchBase):
    """Switch: Pre-Alarm (LED warning before siren) ON/OFF — alarm_settings.preAlarmMode."""

    _field = "preAlarmMode"

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_prealarm"
        self._attr_translation_key = "pre_alarm"
        self._attr_entity_category = EntityCategory.CONFIG


# ─────────────────────────────────────────────────────────────────────────────
class BoschImageRotation180Switch(_BoschSwitchBase, RestoreEntity):
    """Switch: ON = display the camera image rotated 180° (ceiling mount).

    Indoor-only — outdoor cameras have a fixed mounting orientation. Bosch's
    Cloud API does not expose any image-rotation field; this switch is a
    pure client-side display flag with three effects:

      1. `camera.async_camera_image()` rotates the snapshot JPEG via PIL
         before serving it (so push notifications, NAS clips, the dashboard
         snapshot, and any other consumer of /api/camera_proxy/ see the
         right-way-up image).
      2. The Lovelace card applies `transform: rotate(180deg)` to its
         <video> element only — the <img> already comes pre-rotated from
         (1), so rotating it again in CSS would cancel out and leave the
         dashboard snapshot looking upside-down.
      3. For PTZ cameras (Gen1 360), `BoschPanNumber` inverts the sign of
         the pan value so "right" on the slider stays "right" on screen
         even when the camera is upside-down.

    State persists across restarts via RestoreEntity. Default: OFF.
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_image_rotation_180"
        self._attr_translation_key = "image_rotation_180"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def is_on(self) -> bool:
        return bool(self.coordinator.image_rotation_180.get(self._cam_id, False))

    @property
    @override
    def available(self) -> bool:
        # Always available — pure client-side flag, no API dependency
        return self.coordinator.last_update_success

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state == "on":
            self.coordinator.image_rotation_180[self._cam_id] = True
            _LOGGER.debug(
                "image_rotation_180: restored ON for %s from previous state",
                self._cam_id[:8],
            )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        self.coordinator.image_rotation_180[self._cam_id] = True
        self.async_write_ha_state()
        # Notify pan number entity to refresh display value (sign flips).
        self.coordinator.async_update_listeners()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        self.coordinator.image_rotation_180[self._cam_id] = False
        self.async_write_ha_state()
        self.coordinator.async_update_listeners()


# ─────────────────────────────────────────────────────────────────────────────
class BoschPanicAlarmSwitch(_BoschSwitchBase):
    """Switch: trigger the integrated 75 dB siren (Gen2 only).

    PUT /v11/video_inputs/{id}/panic_alarm  body {"status": "ON" | "OFF"} → 204.
    Confirmed via mitmproxy capture of the iOS app (2026-05-13).

    Unlike the Gen1 acoustic_alarm endpoint (auto-stops after a hardware-defined
    duration), panic_alarm is a stateful ON/OFF switch — the siren keeps blaring
    until {"status":"OFF"} is sent or the user disarms via the app.

    State is local-only: the cloud does not expose a "panic active" GET endpoint,
    so we track the last-sent state in `coordinator.panic_alarm_cache`. After a
    restart the switch defaults to OFF (siren has timed out / been silenced).

    Disabled by default — too loud to be in a casual dashboard. User enables via
    Settings → Entities when wiring an "alarm" automation.
    """

    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_panic_alarm"
        self._attr_translation_key = "panic_alarm"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def is_on(self) -> bool:
        cache = getattr(self.coordinator, "panic_alarm_cache", {})
        return bool(cache.get(self._cam_id, False))

    @property
    @override
    def available(self) -> bool:
        return (  # value is correct at runtime; HA/external source is Any-typed
            self.coordinator.last_update_success
            and self.coordinator.is_camera_online(self._cam_id)
        )

    async def _set(self, enabled: bool) -> None:
        if not hasattr(self.coordinator, "panic_alarm_cache"):
            self.coordinator.panic_alarm_cache = {}  # lazy init for older coordinators
        # Privacy mode blocks /panic_alarm with HTTP 443 — warn the user explicitly
        # rather than letting the PUT fail silently and HA's verify-timeout fire.
        if enabled and await _warn_if_privacy_on(self, "Trigger Siren"):
            return
        success = await self.coordinator.async_put_camera(
            self._cam_id, "panic_alarm", {"status": "ON" if enabled else "OFF"}
        )
        if success:
            self.coordinator.panic_alarm_cache[self._cam_id] = enabled
            _LOGGER.info(
                "Panic alarm %s for %s",
                "TRIGGERED" if enabled else "stopped",
                self._cam_title,
            )
        else:
            _LOGGER.warning(
                "Panic alarm %s for %s — PUT /panic_alarm returned non-success",
                "trigger" if enabled else "stop",
                self._cam_title,
            )
        self.async_write_ha_state()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)


# ─────────────────────────────────────────────────────────────────────────────
class BoschNvrRecordingSwitch(_BoschSwitchBase, RestoreEntity):
    """Switch: ON = continuously record this camera's LOCAL stream to disk.

    Phase 1 MVP of the Mini-NVR feature (see `docs/mini-nvr-concept.md`).

    The switch reflects USER INTENT (the persisted state). Whether ffmpeg is
    actually writing files at any given moment also depends on the LAN-only
    gate — when the camera is on the cloud relay or OFFLINE, the switch is
    `available=False` (yellow/grey in the UI) so the user knows recording is
    paused. This is preferred over silently no-op'ing per concept §2.

    LAN-only is a hard line: if the live session falls back to REMOTE the
    recorder stops cleanly. It restarts automatically when the camera is back
    on LOCAL — user does not have to toggle the switch.

    State persists across HA restarts via `RestoreEntity` (mirror of
    `BoschImageRotation180Switch`).
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_nvr_recording_{cam_id.lower()}"
        self._attr_translation_key = "nvr_recording"
        self._attr_entity_category = EntityCategory.CONFIG
        # Opt-in feature — hide from "default-enabled" entity list. User adds
        # the entity manually from the device page if they want it on a card.
        self._attr_entity_registry_enabled_default = False

    @property
    @override
    def is_on(self) -> bool:
        """User intent — True after `async_turn_on`, False after `async_turn_off`.

        Survives HA restarts via RestoreEntity (see `async_added_to_hass`).
        """
        return bool(self.coordinator.nvr_user_intent.get(self._cam_id, False))

    @property
    @override
    def available(self) -> bool:
        """Available only when LAN recording is actually possible.

        Guard rail: surfaces "yellow/grey" in the UI when the camera is on the
        cloud relay or OFFLINE so the user can see at a glance that recording
        is paused (concept §2 — visible state beats silent no-op).
        """
        if not self.coordinator.last_update_success:
            return False
        if not self.coordinator.is_camera_online(self._cam_id):
            return False
        live = self.coordinator.live_connections.get(self._cam_id, {})
        return live.get("_connection_type") == "LOCAL"

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Diagnostic visibility: surface ffmpeg state + last error."""
        proc = self.coordinator.nvr_processes.get(self._cam_id)
        live = self.coordinator.live_connections.get(self._cam_id, {})
        return {
            "ffmpeg_running": proc is not None and proc.returncode is None,
            "connection_type": live.get("_connection_type", "(none)"),
            "last_error": self.coordinator.nvr_error_state.get(self._cam_id, ""),
            "base_path": (
                self.coordinator.options.get("nvr_base_path") or "/config/bosch_nvr"
            ),
            "retention_days": int(
                self.coordinator.options.get("nvr_retention_days", 3)
            ),
        }

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state == "on":
            self.coordinator.nvr_user_intent[self._cam_id] = True
            _LOGGER.debug(
                "NVR: restored ON for %s from previous state",
                self._cam_id[:8],
            )
            # If the LAN session is already up at this point, kick off the
            # recorder immediately. Otherwise the LOCAL-stream-up hook in
            # try_live_connection will start it as soon as a session opens.
            if (
                self.coordinator.last_update_success
                and self.coordinator.is_camera_online(self._cam_id)
                and self.coordinator.live_connections.get(self._cam_id, {}).get(
                    "_connection_type"
                )
                == "LOCAL"
            ):
                self.hass.async_create_task(
                    self.coordinator.start_recorder(self._cam_id),
                    name=f"bosch_nvr_resume_{self._cam_id[:8]}",
                )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        _LOGGER.info("NVR ON for %s", self._cam_title)
        self.coordinator.nvr_user_intent[self._cam_id] = True
        await self.coordinator.start_recorder(self._cam_id)
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        _LOGGER.info("NVR OFF for %s", self._cam_title)
        self.coordinator.nvr_user_intent[self._cam_id] = False
        await self.coordinator.stop_recorder(self._cam_id)
        self.async_write_ha_state()


# ─────────────────────────────────────────────────────────────────────────────
class BoschNvrEventClipSwitch(_BoschSwitchBase, RestoreEntity):
    """Switch: ON (default) = assemble+ship a native clip on FCM motion/person
    events while this camera is in ``event_buffered`` Mini-NVR mode.

    Opt-out for installs that orchestrate their own clip-saving externally
    (e.g. HA automations driving a fork's own service) and don't want a
    second, native clip produced on top of theirs on every event (feature
    request, realKim-dotcom, issue #43 follow-up). Turning this OFF only
    skips `recorder.assemble_and_ship_motion_clip` — the underlying
    pre-roll/post-roll ring buffer keeps running unaffected, since other
    consumers (this switch's whole reason to exist) still need it.

    Always available — unlike `BoschNvrRecordingSwitch` this does not gate
    on the LAN-only recorder path; it purely toggles the FCM-event
    dispatch, which is itself LAN-gated further downstream.

    State persists across HA restarts via RestoreEntity, default ON if no
    previous state (backward compatible with every install predating this
    entity).
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_nvr_event_clip_{cam_id.lower()}"
        self._attr_translation_key = "nvr_event_clip"
        self._attr_entity_category = EntityCategory.CONFIG
        # Opt-in visibility — hide from "default-enabled" entity list, same
        # as BoschNvrRecordingSwitch; most installs never need to touch this.
        self._attr_entity_registry_enabled_default = False

    @property
    @override
    def is_on(self) -> bool:
        return bool(self.coordinator.get_nvr_event_clip_enabled(self._cam_id))

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        # Only act on an explicit on/off — NOT "unavailable"/"unknown" (HA
        # persists those to the restore cache if the coordinator's last
        # update failed at shutdown). This entity defaults to enabled, so
        # blindly writing `last.state == "on"` for a non-on state would
        # silently disable a feature the user never turned off (bug-hunt
        # finding, issue #43 follow-up — the inverse of the gotcha already
        # solved on BoschNvrRecordingSwitch, whose default is off).
        if last is not None and last.state in ("on", "off"):
            self.coordinator.set_nvr_event_clip_enabled(
                self._cam_id, last.state == "on"
            )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        _LOGGER.info("NVR event clip ON for %s", self._cam_title)
        self.coordinator.set_nvr_event_clip_enabled(self._cam_id, True)
        self.async_write_ha_state()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        _LOGGER.info("NVR event clip OFF for %s", self._cam_title)
        self.coordinator.set_nvr_event_clip_enabled(self._cam_id, False)
        self.async_write_ha_state()


# ─────────────────────────────────────────────────────────────────────────────
class BoschExternalStreamSwitch(_BoschSwitchBase, RestoreEntity):
    """Switch: ON = publish stream_url + stream_url_sub sensors for this camera.

    Per-camera opt-in for users who want to paste the LOCAL TLS-proxy RTSP URL
    into an external recorder (Frigate, BlueIris, …). Default OFF to avoid
    entity-spam on installs that only use HA's native streaming.

    When ON, the integration publishes two sensor entities for this camera:
      - sensor.bosch_<name>_stream_url     — main quality (inst=1)
      - sensor.bosch_<name>_stream_url_sub — sub-stream (inst=2), same Bosch
        session, no extra cloud-API quota cost (RTSP is pull-based; quota is
        only consumed when an external client actually connects).

    Both URLs carry Digest credentials inline (the HA TLS proxy is a pure
    TCP-TLS tunnel — FFmpeg / Frigate / BlueIris handle Digest auth
    themselves). For credential-free URLs, a follow-up release will port the
    ioBroker v0.5.3 RTSP-aware Digest-injection proxy.

    State persists across HA restarts via RestoreEntity. No API call —
    purely a client-side flag governing sensor population.
    """

    _attr_entity_registry_enabled_default = False

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_external_stream"
        self._attr_translation_key = "external_stream"
        self._attr_entity_category = EntityCategory.CONFIG

    @property
    @override
    def is_on(self) -> bool:
        return bool(self.coordinator.external_stream_enabled.get(self._cam_id, False))

    @property
    @override
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state == "on":
            self.coordinator.external_stream_enabled[self._cam_id] = True
            _LOGGER.debug(
                "external_stream: restored ON for %s from previous state",
                self._cam_id[:8],
            )

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        self.coordinator.external_stream_enabled[self._cam_id] = True
        self.async_write_ha_state()
        # Notify the two URL sensors so they recompute state immediately.
        self.coordinator.async_update_listeners()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        self.coordinator.external_stream_enabled[self._cam_id] = False
        self.async_write_ha_state()
        self.coordinator.async_update_listeners()


class _BoschFrigateEndpointSwitch(_BoschSwitchBase, RestoreEntity):
    """Base for the per-camera Frigate persistent-endpoint High/Low switches.

    ON = publish the credential-free always-on RTSP URL sensor for this quality
    and (re)start the per-camera front-door. The front-door binds a stable port
    and opens the Bosch LOCAL session lazily when a recorder first connects;
    credentials are injected by the proxy so the URL stays password-free.

    Gated by the global ``frigate_endpoints_enabled`` option — toggling a switch
    while the feature is off records the intent (restored later) but starts
    nothing. State persists across restarts via RestoreEntity.
    """

    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:cctv"
    _attr_entity_category = EntityCategory.CONFIG
    # Subclasses set: _quality ("high"/"low"), _state_map attr name, translation key.
    _quality: str = ""

    def _store(self) -> dict[str, bool]:
        store: dict[str, bool] = (
            self.coordinator.frigate_high_enabled
            if self._quality == "high"
            else self.coordinator.frigate_low_enabled
        )
        return store

    @property
    @override
    def is_on(self) -> bool:
        return bool(self._store().get(self._cam_id, False))

    @property
    @override
    def available(self) -> bool:
        # Always available — this is a CONFIG entity representing user intent
        # (expose this camera to Frigate), not a status that depends on the
        # camera being reachable. Tying available to last_update_success caused
        # the switch to be saved as "unavailable" when the camera went offline;
        # RestoreEntity would then restore with state="unavailable" rather than
        # "on"/"off", and the Frigate URL sensor would stay "Unknown" permanently
        # after a restart (HA#37).
        return True

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state == "on":
            self._store()[self._cam_id] = True
            # Restore the front-door if the global feature is enabled.
            await self.coordinator.async_sync_frigate_endpoint(self._cam_id)

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        self._store()[self._cam_id] = True
        await self.coordinator.async_sync_frigate_endpoint(self._cam_id)
        self.async_write_ha_state()
        self.coordinator.async_update_listeners()

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        self._store()[self._cam_id] = False
        await self.coordinator.async_sync_frigate_endpoint(self._cam_id)
        self.async_write_ha_state()
        self.coordinator.async_update_listeners()


class BoschFrigateHighSwitch(_BoschFrigateEndpointSwitch):
    """Frigate persistent endpoint — High quality (inst=1, main encoder)."""

    _quality = "high"

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_frigate_high"
        self._attr_translation_key = "frigate_high"


class BoschFrigateLowSwitch(_BoschFrigateEndpointSwitch):
    """Frigate persistent endpoint — Low quality (inst=2, sub-stream)."""

    _quality = "low"

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, cam_id, entry)
        self._attr_unique_id = f"bosch_shc_camera_{cam_id}_frigate_low"
        self._attr_translation_key = "frigate_low"

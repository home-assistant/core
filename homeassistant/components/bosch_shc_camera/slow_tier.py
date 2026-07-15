"""Slow-tier per-camera diagnostic pass (largest, most complex piece of
the coordinator tick).

Phase 2 step 7 of the coordinator-rewrite split (see
.claude/plans/jiggly-moseying-peacock.md, project root). Extracted
sub-function by sub-function — see the plan file's "slow_tier.py
internal sub-split" section for the target module layout.

Sub-step 1 added `CamContext`/`_compute_cam_context`: the per-camera
values (hardware generation, online/stream state, the stream-
contention slow-tier defer gate) that the original inline loop
recomputed piecemeal at several different points — computed ONCE here
and threaded through every later sub-function instead.

Sub-step 2 added `_poll_cam_info_caches`: the privacy-mode/camera-
light/notifications-status cache update at the TOP of the per-camera
loop, driven entirely by fields already present in `cam_raw` (from the
`/v11/video_inputs` list fetch) — no network I/O of its own, unlike
every later sub-function in this module.

Sub-step 3 added `_poll_cam_control`: the two small every-tick (not
slow-tier-gated) fetches — pan position (cameras with `panLimit`) and
Gen2 lighting/switch state (polled every tick because the Bosch app
itself polls it ~every 40s, faster than the 300s slow-tier interval
would allow).

Sub-step 4 (the single highest-risk sub-step of the whole rewrite,
per the plan) adds `_poll_slow_tier_endpoints`: the 10-20-endpoint
parallel `asyncio.gather` fetch that only runs on the ~5-min slow-tier
interval (`ctx.do_slow_cam and ctx.is_online`), plus its full
per-endpoint result dispatcher (wifiinfo/firmware/zones/alarm/etc.,
many gated by `coordinator.is_write_locked(...)` to avoid reverting a
just-written optimistic cache value). Takes a `fire_intrusion_event`
callable instead of calling `coordinator._maybe_fire_intrusion_event`
directly — the original inline code called that via
`BoschCameraCoordinator._maybe_fire_intrusion_event(self, ...)` class
dispatch specifically to tolerate `SimpleNamespace` test-fixture
coordinators that don't set it as a bound attribute; a plain
`coordinator.<name>` call here would break those existing tests, and
importing `BoschCameraCoordinator` at runtime would be circular (this
module is imported BY `__init__.py`). The caller in `__init__.py`
passes a closure that does the exact same class-dispatch.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
import time
from typing import TYPE_CHECKING, Any

import aiohttp

from .const import CLOUD_API, SLOW_TIER_MAX_DEFER_SEC
from .models import get_model_config

if TYPE_CHECKING:  # pragma: no cover — only for type hints
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


def _err_str(err: BaseException) -> str:
    """Format an exception so empty-message types (TimeoutError, some
    aiohttp errors) still produce meaningful log output. Falls back to
    repr(err) when str(err) is empty.

    Deliberately NOT `coordinator.err_str(err)` — that is a
    `@staticmethod` on `BoschCameraCoordinator` called via CLASS
    dispatch (`BoschCameraCoordinator.err_str(err)`) in the original
    inline code specifically because unit-test fixtures across the
    suite inject `SimpleNamespace` stubs as the coordinator (no
    `__init__`, so no instance attribute lookup fallback works either).
    Re-implementing the 3-line logic here avoids depending on either.
    """
    s = str(err)
    return s or repr(err)


@dataclass
class CamContext:
    """Per-camera values computed once per tick, shared by every
    slow-tier sub-function — avoids the original inline loop's
    redundant re-derivation of `hw`/`is_gen2` at multiple points.
    """

    hw: str
    is_gen2: bool
    is_online: bool
    stream_active: bool
    local_stream_active: bool
    privacy_on: bool
    do_slow_cam: bool
    pan_limit: int
    has_light: bool


def _compute_cam_context(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    cam_raw: dict[str, Any],
    data: dict[str, Any],
    opts: dict[str, Any],
    do_slow: bool,
) -> CamContext:
    """Compute the per-camera context for the slow-tier pass, including
    the stream-contention defer-gate side effects (mutates
    `coordinator.slow_tier_deferred`/`_slow_tier_defer_since`).
    """
    cam_status = data[cam_id].get("status", "UNKNOWN")
    is_online = cam_status == "ONLINE"

    hw = cam_raw.get("hardwareVersion", "")
    is_gen2 = get_model_config(hw).generation >= 2
    feat_support = cam_raw.get("featureSupport", {})
    pan_limit = feat_support.get("panLimit", 0)
    has_light = feat_support.get("light", False)

    # Stream-contention gate (Root-Cause: stream-freeze-on-motion-event-
    # contention.md, 2026-06-12): the Gen2 camera exposes ONE TLS control
    # channel shared by the RTSP keepalive AND every RCP / cloud slow-tier
    # read. When both compete, OPTIONS RTT grows from ~1 s to ~21 s against
    # a 30-s RTSP session timeout → go2rtc EOF → 5-10 s video freeze.
    # Fix: defer (NOT drop) the slow-tier fetch for a camera while its live
    # stream is active. The next coordinator tick where the stream is idle
    # picks it up via _slow_tier_deferred. A *continuously* active stream
    # (dashboard left on live view) never goes idle, so the deferral is
    # bounded by SLOW_TIER_MAX_DEFER_SEC: once exceeded we force one read
    # despite the stream, then restart the cycle — no permanent staleness.
    # Partial coordinator stubs in unit tests bypass __init__ and may
    # lack these attributes; the real coordinator always sets them in
    # __init__. Lazy-init keeps the gate robust without forcing every
    # stub to mirror the fields.
    # The real coordinator always sets a `BoolFieldView` here (Session-State-
    # Facade Slice 1, see session_state.py) — a plain set is only ever
    # assigned on a bare test stub, never on the real class, hence the
    # ignore comment below.
    if not hasattr(coordinator, "slow_tier_deferred"):
        coordinator.slow_tier_deferred = set()  # type: ignore[assignment]
    if not hasattr(coordinator, "slow_tier_defer_since"):
        coordinator.slow_tier_defer_since = {}
    stream_active = cam_id in coordinator.live_connections
    # Option: defer slow-tier when stream is active (default ON).
    # When OFF, slow-tier runs regardless — diagnostic sensors stay
    # current during streaming at the cost of potential TLS contention.
    _defer_diag = bool(opts.get("defer_diag_during_stream", True))
    # Bounded defer: a deferral that has lasted ≥ the cap must yield one
    # read even while the stream is live, else diagnostics freeze forever.
    _defer_started = coordinator.slow_tier_defer_since.get(cam_id)
    defer_bound_reached = (
        _defer_started is not None
        and time.monotonic() - _defer_started >= SLOW_TIER_MAX_DEFER_SEC
    )
    # per-camera slow flag: True on the normal interval, OR when a deferred
    # fetch is now safe to run (stream gone idle since last deferral).
    do_slow_cam = (
        do_slow
        or (cam_id in coordinator.slow_tier_deferred and not stream_active)
        or defer_bound_reached
    )
    if _defer_diag and do_slow_cam and stream_active and not defer_bound_reached:
        # Defer: stream is live — adding to deferred set instead of running.
        coordinator.slow_tier_deferred.add(cam_id)
        coordinator.slow_tier_defer_since.setdefault(cam_id, time.monotonic())
        _LOGGER.debug(
            "Slow-tier deferred for %s (live stream active)",
            cam_id,
        )
        do_slow_cam = False  # skip the fetch blocks below for this camera
    elif do_slow_cam and cam_id in coordinator.slow_tier_deferred:
        # Deferred fetch now safe: stream gone idle, defer disabled, or the
        # defer bound was reached (forced read despite an active stream).
        coordinator.slow_tier_deferred.discard(cam_id)
        coordinator.slow_tier_defer_since.pop(cam_id, None)
        _LOGGER.debug(
            "Slow-tier running deferred fetch for %s (%s)",
            cam_id,
            "defer bound reached, stream still active"
            if defer_bound_reached and stream_active
            else "stream now idle",
        )
    if do_slow_cam and not is_online:
        _LOGGER.debug("Slow-tier skipped for %s (%s)", cam_id, cam_status.lower())

    local_stream_active = (
        cam_id in coordinator.live_connections
        and coordinator.live_connections[cam_id].get("_connection_type") == "LOCAL"
    )
    privacy_on = cam_raw.get("privacyMode", "").upper() == "ON"

    return CamContext(
        hw=hw,
        is_gen2=is_gen2,
        is_online=is_online,
        stream_active=stream_active,
        local_stream_active=local_stream_active,
        privacy_on=privacy_on,
        do_slow_cam=do_slow_cam,
        pan_limit=pan_limit,
        has_light=has_light,
    )


def _poll_cam_info_caches(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    cam_raw: dict[str, Any],
) -> None:
    """Update `coordinator.shc_state_cache[cam_id]` from fields already
    present in `cam_raw` (privacy mode, camera-light state, notifications
    status) — no network I/O, unlike every later slow-tier sub-function.
    """
    privacy_str = cam_raw.get("privacyMode", "")
    feat_support = cam_raw.get("featureSupport", {})
    has_light = feat_support.get("light", False)
    feat_status = cam_raw.get("featureStatus", {})
    light_on = feat_status.get("frontIlluminatorInGeneralLightOn")

    cache = coordinator.shc_state_cache.setdefault(
        cam_id,
        {
            "device_id": None,
            "camera_light": None,
            "front_light": None,
            "wallwasher": None,
            "front_light_intensity": None,
            "privacy_mode": None,
            "has_light": False,
            "notifications_status": None,
        },
    )
    # Cloud is authoritative for privacy (fast, always available).
    # Skip overwrite if a write happened within _WRITE_LOCK_SECS — same
    # propagation-delay race as camera light.
    privacy_locked = (
        cam_id in coordinator.privacy_set_at
        and (time.monotonic() - coordinator.privacy_set_at[cam_id])
        < coordinator.WRITE_LOCK_SECS
    )
    if privacy_str and not privacy_locked:
        new_privacy = privacy_str.upper() == "ON"
        old_privacy = cache.get("privacy_mode")
        cache["privacy_mode"] = new_privacy
        # Hardware/external privacy trigger detection.
        # When the cam's physical privacy button is pressed (or someone
        # toggles privacy in the Bosch app), the cloud reports
        # privacyMode=ON but our `BoschPrivacyModeSwitch.async_turn_on`
        # — which is the only path that calls `_tear_down_live_stream`
        # — never runs. The result is a stuck `state: streaming`,
        # the live-stream switch frozen on `on`, and the TLS proxy
        # entering an endless reconnect loop against the now-gone
        # camera (Errno 113 Host unreachable). We detect the
        # OFF→ON transition here and schedule the same teardown
        # the user-toggle path uses.
        if (
            new_privacy is True
            and old_privacy is not True
            and coordinator.live_connections.get(cam_id)
        ):
            _LOGGER.info(
                "Privacy ON detected externally for %s — tearing down active stream",
                cam_id[:8],
            )
            coordinator.hass.async_create_task(
                coordinator.tear_down_live_stream(cam_id)
            )
    cache["has_light"] = has_light
    # Use cloud featureStatus for light state; SHC supplements if available.
    # Skip overwrite if a write happened within _WRITE_LOCK_SECS — the cloud
    # API returns stale data briefly after a PUT /lighting_override, which
    # would flip the switch back to OFF right after the user turned it ON.
    light_locked = (
        cam_id in coordinator.light_set_at
        and (time.monotonic() - coordinator.light_set_at[cam_id])
        < coordinator.WRITE_LOCK_SECS
    )
    if light_on is not None and not light_locked:
        # Gen2: Use lighting/switch cache for actual light state
        # (featureStatus reports config state, not physical on/off)
        _hw = cam_raw.get("hardwareVersion", "CAMERA")
        if get_model_config(_hw).generation >= 2:
            # Gen2: Only update light state from lighting/switch cache
            # Do NOT use featureStatus (reports config, not physical state)
            # If cache not yet populated, keep current state (don't overwrite)
            lsc = coordinator.lighting_switch_cache.get(cam_id)
            if lsc:
                front_bri = lsc.get("frontLightSettings", {}).get("brightness", 0)
                top_bri = lsc.get("topLedLightSettings", {}).get("brightness", 0)
                bot_bri = lsc.get("bottomLedLightSettings", {}).get("brightness", 0)
                cache["front_light"] = front_bri > 0
                cache["wallwasher"] = top_bri > 0 or bot_bri > 0
                cache["camera_light"] = front_bri > 0 or top_bri > 0 or bot_bri > 0
                cache["front_light_intensity"] = front_bri / 100.0 if front_bri else 0.0
            # else: keep current cache values, don't overwrite from featureStatus
        else:
            cache["camera_light"] = light_on
            cache["front_light"] = feat_status.get("frontIlluminatorInGeneralLightOn")
            cache["wallwasher"] = feat_status.get("wallwasherInGeneralLightOn")
            intensity = feat_status.get("frontIlluminatorGeneralLightIntensity")
            if intensity is not None:
                cache["front_light_intensity"] = intensity
    elif cache.get("camera_light") is None:
        cache["camera_light"] = None
    # Read notifications status from cloud API response.
    # Skip overwrite if written recently (same propagation-delay race as light).
    notif_status = cam_raw.get("notificationsEnabledStatus", "")
    notif_locked = (
        cam_id in coordinator.notif_set_at
        and (time.monotonic() - coordinator.notif_set_at[cam_id])
        < coordinator.WRITE_LOCK_SECS
    )
    if notif_status and not notif_locked:
        cache["notifications_status"] = notif_status


async def _poll_cam_control(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    ctx: CamContext,
    session: aiohttp.ClientSession,
    headers: dict[str, str],
) -> None:
    """Fetch pan position + Gen2 lighting/switch state — both polled
    every tick (NOT slow-tier-gated), only gated on `ctx.is_online`.
    """
    # Fetch pan position for cameras that support it (skip if offline)
    if ctx.pan_limit and ctx.is_online:
        try:
            async with asyncio.timeout(5):
                async with session.get(
                    f"{CLOUD_API}/v11/video_inputs/{cam_id}/pan",
                    headers=headers,
                ) as pan_resp:
                    if pan_resp.status == 200:
                        pan_data = await pan_resp.json()
                        coordinator.pan_cache[cam_id] = pan_data.get(
                            "currentAbsolutePosition"
                        )
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug(
                "Pan fetch error for %s: %s",
                cam_id,
                _err_str(err),
            )

    # ── Gen2 lighting/switch — fetched every tick (60s) ──
    # Bosch app polls this every ~40s. Slow tier (300s) is too slow
    # for responsive light state sync when lights are changed via the app.
    if ctx.is_online and ctx.is_gen2:
        try:
            async with asyncio.timeout(5):
                async with session.get(
                    f"{CLOUD_API}/v11/video_inputs/{cam_id}/lighting/switch",
                    headers=headers,
                ) as ls_resp:
                    if ls_resp.status == 200:
                        coordinator.lighting_switch_cache[cam_id] = await ls_resp.json()
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug(
                "lighting/switch fetch error for %s: %s",
                cam_id,
                _err_str(err),
            )


async def _poll_slow_tier_endpoints(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    cam_raw: dict[str, Any],
    ctx: CamContext,
    data: dict[str, Any],
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    fire_intrusion_event: Callable[[str, str, dict[str, Any]], None],
) -> None:
    """Slow-tier (~5-min interval) parallel endpoint fetch + result
    dispatch: wifiinfo, ambient light, motion, firmware, recording
    options, unread-events count, commissioned, timestamp,
    notifications, rules, zones/privateAreas or motion-sensitive-areas/
    privacy-masks, privacy-sound-override, autofollow, lighting-options,
    and (Gen2-only) ledlights/lens-elevation/audio/lighting-*/
    intrusion-detection/audio-detection, plus (Gen2 Indoor II-only)
    alarm settings/status/icon-LED-brightness.

    Only runs when `ctx.do_slow_cam and ctx.is_online` (skipped when
    camera is offline or session-quota hit — endpoints would return
    444 too, and the camera isn't truly unreachable).
    """
    if not (ctx.do_slow_cam and ctx.is_online):
        return

    # ── Parallel slow-tier fetch ──────────────────────────────
    # All endpoints are independent — fetch in parallel with
    # asyncio.gather() instead of sequentially.
    # Reduces slow-tier from ~13×5s = 65s to ~5s (single timeout).
    hw = ctx.hw
    pan_limit = ctx.pan_limit

    async def _fetch(
        endpoint: str,
    ) -> tuple[str, int, dict[str, Any] | list[Any] | int | float | str | None]:
        """Fetch a single slow-tier endpoint. Returns (endpoint, status, data)."""
        try:
            async with asyncio.timeout(8):
                async with (
                    session.get(
                        f"{CLOUD_API}/v11/video_inputs/{cam_id}/{endpoint}",  # closure awaited within the same loop iteration
                        headers=headers,
                    ) as r
                ):
                    if r.status == 200:
                        return (endpoint, 200, await r.json())
                    return (endpoint, r.status, None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug(
                "%s fetch error for %s: %s",
                endpoint,
                cam_id,  # closure awaited within the same loop iteration
                _err_str(err),
            )
            return (endpoint, 0, None)

    # Build task list (skip endpoints not applicable to this camera)
    is_gen2 = ctx.is_gen2
    endpoints = [
        "wifiinfo",
        "ambient_light_sensor_level",
        "motion",
        "firmware",
        "recording_options",
        "unread_events_count",
        "commissioned",
        "timestamp",
        "notifications",
        "rules",
    ]
    # Gen1 uses motion_sensitive_areas + privacy_masks (rectangles)
    # Gen2 Outdoor II uses zones + privateAreas (polygons) — different endpoints!
    # Gen2 Indoor II returns 442 ("hardware not supported") on privateAreas
    # — confirmed by direct API test 2026-04-11. Only poll zones.
    if is_gen2:
        endpoints.append("zones")
        if hw not in ("HOME_Eyes_Indoor", "CAMERA_INDOOR_GEN2"):
            endpoints.append("privateAreas")
    else:
        endpoints.extend(["motion_sensitive_areas", "privacy_masks"])
    if hw in (
        "INDOOR",
        "CAMERA_360",
        "HOME_Eyes_Indoor",
        "CAMERA_INDOOR_GEN2",
    ):
        endpoints.append("privacy_sound_override")
    if pan_limit:
        endpoints.append("autofollow")
    if ctx.has_light:
        endpoints.append("lighting_options")

    # Gen2-only endpoints
    if is_gen2:
        endpoints.extend(
            [
                "ledlights",
                "lens_elevation",
                "audio",
                "lighting/motion",
                "lighting/ambient",
                "lighting",
                "intrusionDetectionConfig",
                "audioDetectionConfig",
            ]
        )
    # Gen2 Indoor II-only endpoints (alarm system + power-LED).
    # privacy_sound_override is added above (same as Gen1 Indoor).
    if hw in ("HOME_Eyes_Indoor", "CAMERA_INDOOR_GEN2"):
        endpoints.extend(
            [
                "alarm_settings",
                "alarmStatus",
                "iconLedBrightness",
            ]
        )

    results = await asyncio.gather(
        *[_fetch(ep) for ep in endpoints],
        return_exceptions=True,
    )

    # Process results
    for fetch_result in results:
        if isinstance(fetch_result, BaseException):
            continue
        ep, ep_status, ep_data = fetch_result
        if ep_status != 200 or ep_data is None:
            continue
        if ep == "wifiinfo":
            # isinstance guard — see the "ambient_light_sensor_level" branch
            # below (chaos-fault-injection regression) for why this is
            # required. A malformed-but-200 body is skipped rather than
            # overwriting a previously-good cached value.
            if isinstance(ep_data, dict):
                coordinator.wifiinfo_cache[cam_id] = ep_data
        elif ep == "ambient_light_sensor_level":
            # isinstance guard (chaos-fault-injection regression,
            # tests/test_chaos_fault_injection.py): every sibling branch in
            # this loop already guards against a malformed-but-200 body
            # (a JSON array/string/number instead of an object) — this one
            # didn't, so a single such response from the cloud raised an
            # unhandled AttributeError that propagated out of
            # `_poll_slow_tier_endpoints` uncaught (the `_fetch` closure's
            # try/except only covers network-level failures, not shape
            # validation of an already-200 body) and crashed the WHOLE
            # coordinator tick — `_async_update_data`'s outer handler only
            # catches `UpdateFailed`/`TimeoutError`/`aiohttp.ClientError`,
            # not AttributeError.
            coordinator.ambient_light_cache[cam_id] = (
                ep_data.get("ambientLightSensorLevel")
                if isinstance(ep_data, dict)
                else None
            )
        elif ep == "motion":
            # Skip within the write-lock window so a poll that
            # lands before the cloud reflects the user's
            # sensitivity change doesn't revert the UI.
            if not coordinator.is_write_locked(cam_id, coordinator.motion_set_at):
                data[cam_id]["motion"] = ep_data
        elif ep == "firmware":
            # Write-locked like motion/privacy_sound_override above —
            # otherwise a poll landing right after async_install()'s
            # optimistic updating=True (before Bosch's backend has
            # actually flagged the install) reverts it to stale
            # "not updating" and a second install PUT could fire.
            # isinstance guard — see the "ambient_light_sensor_level" branch
            # below (chaos-fault-injection regression) for why this is
            # required.
            if not coordinator.is_write_locked(
                cam_id, coordinator.firmware_set_at
            ) and isinstance(ep_data, dict):
                coordinator.firmware_cache[cam_id] = ep_data
        elif ep == "recording_options":
            data[cam_id]["recordingOptions"] = ep_data
        elif ep == "unread_events_count":
            if isinstance(ep_data, dict):
                coordinator.unread_events_cache[cam_id] = int(
                    ep_data.get("count", ep_data.get("result", 0)) or 0
                )
            elif isinstance(ep_data, (int, float)):
                coordinator.unread_events_cache[cam_id] = int(ep_data)
        elif ep == "privacy_sound_override":
            # isinstance guard — see the "ambient_light_sensor_level" branch
            # above (chaos-fault-injection regression) for why this is
            # required: an unguarded `.get()` on a malformed-but-200 body
            # crashes the whole coordinator tick uncaught.
            if not coordinator.is_write_locked(
                cam_id, coordinator.privacy_sound_set_at
            ):
                coordinator.privacy_sound_cache[cam_id] = (
                    ep_data.get("result", False) if isinstance(ep_data, dict) else False
                )
        elif ep == "commissioned":
            # isinstance guard — see the "ambient_light_sensor_level" branch
            # above (chaos-fault-injection regression) for why this is
            # required.
            if isinstance(ep_data, dict):
                coordinator.commissioned_cache[cam_id] = ep_data
        elif ep == "autofollow":
            data[cam_id]["autofollow"] = ep_data
        elif ep == "timestamp":
            # isinstance guard — see the "ambient_light_sensor_level" branch
            # above (chaos-fault-injection regression) for why this is
            # required.
            if not coordinator.is_write_locked(cam_id, coordinator.timestamp_set_at):
                coordinator.timestamp_cache[cam_id] = (
                    ep_data.get("result", False) if isinstance(ep_data, dict) else False
                )
        elif ep == "notifications":
            # isinstance guard — see the "ambient_light_sensor_level" branch
            # above (chaos-fault-injection regression) for why this is
            # required.
            if isinstance(ep_data, dict):
                coordinator.notifications_cache[cam_id] = ep_data
        elif ep == "rules":
            coordinator.rules_cache[cam_id] = (
                ep_data if isinstance(ep_data, list) else []
            )
        elif ep == "motion_sensitive_areas":
            coordinator.cloud_zones_cache[cam_id] = (
                ep_data if isinstance(ep_data, list) else []
            )
        elif ep == "privacy_masks":
            coordinator.cloud_privacy_masks_cache[cam_id] = (
                ep_data if isinstance(ep_data, list) else []
            )
        elif ep == "lighting_options":
            # Write-locked like motion/privacy_sound_override above — otherwise
            # a poll landing before Bosch's cloud reflects a set_lighting_schedule
            # write can revert the cache to the stale pre-write schedule.
            if not coordinator.is_write_locked(
                cam_id, coordinator.lighting_options_set_at
            ):
                coordinator.lighting_options_cache[cam_id] = (
                    ep_data if isinstance(ep_data, dict) else {}
                )
        elif ep == "ledlights":
            if not coordinator.is_write_locked(cam_id, coordinator.ledlights_set_at):
                coordinator.ledlights_cache[cam_id] = (
                    ep_data.get("state") == "ON" if isinstance(ep_data, dict) else None
                )
        elif ep == "lens_elevation":
            coordinator.lens_elevation_cache[cam_id] = (
                ep_data.get("elevation") if isinstance(ep_data, dict) else None
            )
        elif ep == "audio":
            coordinator.audio_cache[cam_id] = (
                ep_data if isinstance(ep_data, dict) else {}
            )
        elif ep == "lighting/motion":
            coordinator.motion_light_cache[cam_id] = (
                ep_data if isinstance(ep_data, dict) else {}
            )
            # MotionLightSwitch state is synced via switch._is_on
            # on its next update — nothing to do here.
        elif ep == "lighting/ambient":
            coordinator.ambient_lighting_cache[cam_id] = (
                ep_data if isinstance(ep_data, dict) else {}
            )
        elif ep == "lighting":
            coordinator.global_lighting_cache[cam_id] = (
                ep_data if isinstance(ep_data, dict) else {}
            )
        elif ep == "intrusionDetectionConfig":
            # Skip cache overwrite within the write-lock window —
            # otherwise a slow-tier poll hitting before the cloud
            # has caught up to the user's toggle reverts the
            # switch back to the stale enabled value.
            if not coordinator.is_write_locked(
                cam_id, coordinator.intrusion_config_set_at
            ):
                coordinator.intrusion_config_cache[cam_id] = (
                    ep_data if isinstance(ep_data, dict) else {}
                )
        elif ep == "audioDetectionConfig":
            # Glass-break / fire-alarm sound detection (Gen2
            # Audio-Plus). Skip cache overwrite within the
            # write-lock window so an optimistic toggle isn't
            # reverted by a slow-tier poll before cloud catches up.
            if not coordinator.is_write_locked(
                cam_id, coordinator.audio_detection_set_at
            ):
                coordinator.audio_detection_cache[cam_id] = (
                    ep_data if isinstance(ep_data, dict) else {}
                )
        elif ep == "alarm_settings":
            # Skip within the write-lock window (cloud
            # propagation) so the optimistic cache isn't reverted.
            if not coordinator.is_write_locked(
                cam_id, coordinator.alarm_settings_set_at
            ):
                coordinator.alarm_settings_cache[cam_id] = (
                    ep_data if isinstance(ep_data, dict) else {}
                )
        elif ep == "alarmStatus":
            # Actual response format confirmed 2026-04-11:
            #   {"alarmType": "NONE" | ..., "intrusionSystem": "INACTIVE" | "ACTIVE" | ...}
            coordinator.alarm_status_cache[cam_id] = (
                ep_data if isinstance(ep_data, dict) else {}
            )
            if isinstance(ep_data, dict) and not coordinator.is_write_locked(
                cam_id, coordinator.arming_set_at
            ):
                intrusion = str(ep_data.get("intrusionSystem", "")).upper()
                if intrusion == "ACTIVE":
                    coordinator.arming_cache[cam_id] = True
                elif intrusion == "INACTIVE":
                    coordinator.arming_cache[cam_id] = False
            if isinstance(ep_data, dict):
                fire_intrusion_event(
                    cam_id,
                    cam_raw.get("title", cam_id),
                    ep_data,
                )
        elif ep == "iconLedBrightness":
            # Power-LED brightness 0-4 (5 discrete steps: off + 4 levels)
            try:
                val = int(ep_data.get("value", 0)) if isinstance(ep_data, dict) else 0
                coordinator.icon_led_brightness_cache[cam_id] = max(0, min(4, val))
            except TypeError, ValueError:
                coordinator.icon_led_brightness_cache[cam_id] = 0
        elif ep == "zones":
            zones_data: list[Any] = ep_data if isinstance(ep_data, list) else []
            coordinator.gen2_zones_cache[cam_id] = zones_data
            _LOGGER.debug(
                "Gen2 zones for %s: %d zones fetched",
                cam_id[:8],
                len(zones_data),
            )
        elif ep == "privateAreas":
            areas_data: list[Any] = ep_data if isinstance(ep_data, list) else []
            coordinator.gen2_private_areas_cache[cam_id] = areas_data
            _LOGGER.debug(
                "Gen2 privateAreas for %s: %d areas fetched",
                cam_id[:8],
                len(areas_data),
            )

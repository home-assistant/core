"""Slow-tier per-camera diagnostic pass — the largest, most complex piece of the coordinator tick.

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

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
import time
from typing import TYPE_CHECKING, Any

import aiohttp

from .const import CLOUD_API
from .models import get_model_config

if TYPE_CHECKING:  # pragma: no cover — only for type hints
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


def err_str(err: BaseException) -> str:
    """Format an exception so empty-message types still produce useful output.

    Covers TimeoutError and some aiohttp errors. Falls back to repr(err)
    when str(err) is empty.

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
    """Per-camera values computed once per tick, shared by every slow-tier sub-function.

    Avoids the original inline loop's redundant re-derivation of
    `hw`/`is_gen2` at multiple points.
    """

    hw: str
    is_gen2: bool
    is_online: bool
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
    """Compute the per-camera context for the slow-tier pass."""
    cam_status = data[cam_id].get("status", "UNKNOWN")
    is_online = cam_status == "ONLINE"

    hw = cam_raw.get("hardwareVersion", "")
    is_gen2 = get_model_config(hw).generation >= 2
    feat_support = cam_raw.get("featureSupport", {})
    pan_limit = feat_support.get("panLimit", 0)
    has_light = feat_support.get("light", False)

    do_slow_cam = do_slow
    if do_slow_cam and not is_online:
        _LOGGER.debug("Slow-tier skipped for %s (%s)", cam_id, cam_status.lower())

    privacy_on = cam_raw.get("privacyMode", "").upper() == "ON"

    return CamContext(
        hw=hw,
        is_gen2=is_gen2,
        is_online=is_online,
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
    """Update `coordinator.shc_state_cache[cam_id]` from fields already present in `cam_raw`.

    Covers privacy mode, camera-light state, notifications status — no
    network I/O, unlike every later slow-tier sub-function.
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
    # Skip overwrite if a write happened within WRITE_LOCK_SECS — same
    # propagation-delay race as camera light.
    privacy_locked = (
        cam_id in coordinator.privacy_set_at
        and (time.monotonic() - coordinator.privacy_set_at[cam_id])
        < coordinator.WRITE_LOCK_SECS
    )
    if privacy_str and not privacy_locked:
        new_privacy = privacy_str.upper() == "ON"
        cache["privacy_mode"] = new_privacy
    cache["has_light"] = has_light
    # Use cloud featureStatus for light state; SHC supplements if available.
    # Skip overwrite if a write happened within WRITE_LOCK_SECS — the cloud
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
    """Fetch pan position + Gen2 lighting/switch state.

    Both polled every tick (NOT slow-tier-gated), only gated on
    `ctx.is_online`.
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
                err_str(err),
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
                err_str(err),
            )


def _slow_tier_endpoint_list(ctx: CamContext) -> list[str]:
    """Build the list of slow-tier endpoints applicable to this camera."""
    hw = ctx.hw
    pan_limit = ctx.pan_limit
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
    return endpoints


@dataclass
class _SlowTierResult:
    """Bundles everything a single-endpoint handler needs."""

    coordinator: BoschCameraCoordinator
    cam_id: str
    cam_raw: dict[str, Any]
    data: dict[str, Any]
    fire_intrusion_event: Callable[[str, str, dict[str, Any]], None]
    ep_data: Any


def _handle_wifiinfo(r: _SlowTierResult) -> None:
    # isinstance guard — see `_handle_ambient_light_sensor_level` for why
    # this is required. A malformed-but-200 body is skipped rather than
    # overwriting a previously-good cached value.
    if isinstance(r.ep_data, dict):
        r.coordinator.wifiinfo_cache[r.cam_id] = r.ep_data


def _handle_ambient_light_sensor_level(r: _SlowTierResult) -> None:
    # isinstance guard (chaos-fault-injection regression,
    # tests/test_chaos_fault_injection.py): every sibling handler here
    # already guards against a malformed-but-200 body (a JSON array/string/
    # number instead of an object) — this one didn't, so a single such
    # response from the cloud raised an unhandled AttributeError that
    # propagated out of `_poll_slow_tier_endpoints` uncaught (the `_fetch`
    # closure's try/except only covers network-level failures, not shape
    # validation of an already-200 body) and crashed the WHOLE coordinator
    # tick — `_async_update_data`'s outer handler only catches
    # `UpdateFailed`/`TimeoutError`/`aiohttp.ClientError`, not AttributeError.
    r.coordinator.ambient_light_cache[r.cam_id] = (
        r.ep_data.get("ambientLightSensorLevel")
        if isinstance(r.ep_data, dict)
        else None
    )


def _handle_motion(r: _SlowTierResult) -> None:
    # Skip within the write-lock window so a poll that lands before the
    # cloud reflects the user's sensitivity change doesn't revert the UI.
    if not r.coordinator.is_write_locked(r.cam_id, r.coordinator.motion_set_at):
        r.data[r.cam_id]["motion"] = r.ep_data


def _handle_firmware(r: _SlowTierResult) -> None:
    # Write-locked like motion/privacy_sound_override — otherwise a poll
    # landing right after async_install()'s optimistic updating=True (before
    # Bosch's backend has actually flagged the install) reverts it to stale
    # "not updating" and a second install PUT could fire.
    if not r.coordinator.is_write_locked(
        r.cam_id, r.coordinator.firmware_set_at
    ) and isinstance(r.ep_data, dict):
        r.coordinator.firmware_cache[r.cam_id] = r.ep_data


def _handle_recording_options(r: _SlowTierResult) -> None:
    r.data[r.cam_id]["recordingOptions"] = r.ep_data


def _handle_unread_events_count(r: _SlowTierResult) -> None:
    if isinstance(r.ep_data, dict):
        r.coordinator.unread_events_cache[r.cam_id] = int(
            r.ep_data.get("count", r.ep_data.get("result", 0)) or 0
        )
    elif isinstance(r.ep_data, (int, float)):
        r.coordinator.unread_events_cache[r.cam_id] = int(r.ep_data)


def _handle_privacy_sound_override(r: _SlowTierResult) -> None:
    # isinstance guard: an unguarded `.get()` on a malformed-but-200 body
    # crashes the whole coordinator tick uncaught (see ambient-light handler).
    if not r.coordinator.is_write_locked(r.cam_id, r.coordinator.privacy_sound_set_at):
        r.coordinator.privacy_sound_cache[r.cam_id] = (
            r.ep_data.get("result", False) if isinstance(r.ep_data, dict) else False
        )


def _handle_commissioned(r: _SlowTierResult) -> None:
    if isinstance(r.ep_data, dict):
        r.coordinator.commissioned_cache[r.cam_id] = r.ep_data


def _handle_autofollow(r: _SlowTierResult) -> None:
    r.data[r.cam_id]["autofollow"] = r.ep_data


def _handle_timestamp(r: _SlowTierResult) -> None:
    if not r.coordinator.is_write_locked(r.cam_id, r.coordinator.timestamp_set_at):
        r.coordinator.timestamp_cache[r.cam_id] = (
            r.ep_data.get("result", False) if isinstance(r.ep_data, dict) else False
        )


def _handle_notifications(r: _SlowTierResult) -> None:
    if isinstance(r.ep_data, dict):
        r.coordinator.notifications_cache[r.cam_id] = r.ep_data


def _handle_rules(r: _SlowTierResult) -> None:
    r.coordinator.rules_cache[r.cam_id] = (
        r.ep_data if isinstance(r.ep_data, list) else []
    )


def _handle_motion_sensitive_areas(r: _SlowTierResult) -> None:
    r.coordinator.cloud_zones_cache[r.cam_id] = (
        r.ep_data if isinstance(r.ep_data, list) else []
    )


def _handle_privacy_masks(r: _SlowTierResult) -> None:
    r.coordinator.cloud_privacy_masks_cache[r.cam_id] = (
        r.ep_data if isinstance(r.ep_data, list) else []
    )


def _handle_lighting_options(r: _SlowTierResult) -> None:
    # Write-locked like motion/privacy_sound_override — otherwise a poll
    # landing before Bosch's cloud reflects a set_lighting_schedule write
    # can revert the cache to the stale pre-write schedule.
    if not r.coordinator.is_write_locked(
        r.cam_id, r.coordinator.lighting_options_set_at
    ):
        r.coordinator.lighting_options_cache[r.cam_id] = (
            r.ep_data if isinstance(r.ep_data, dict) else {}
        )


def _handle_ledlights(r: _SlowTierResult) -> None:
    if not r.coordinator.is_write_locked(r.cam_id, r.coordinator.ledlights_set_at):
        r.coordinator.ledlights_cache[r.cam_id] = (
            r.ep_data.get("state") == "ON" if isinstance(r.ep_data, dict) else None
        )


def _handle_lens_elevation(r: _SlowTierResult) -> None:
    r.coordinator.lens_elevation_cache[r.cam_id] = (
        r.ep_data.get("elevation") if isinstance(r.ep_data, dict) else None
    )


def _handle_audio(r: _SlowTierResult) -> None:
    r.coordinator.audio_cache[r.cam_id] = (
        r.ep_data if isinstance(r.ep_data, dict) else {}
    )


def _handle_lighting_motion(r: _SlowTierResult) -> None:
    # MotionLightSwitch state is synced via switch._is_on on its next
    # update — nothing further to do here.
    r.coordinator.motion_light_cache[r.cam_id] = (
        r.ep_data if isinstance(r.ep_data, dict) else {}
    )


def _handle_lighting_ambient(r: _SlowTierResult) -> None:
    r.coordinator.ambient_lighting_cache[r.cam_id] = (
        r.ep_data if isinstance(r.ep_data, dict) else {}
    )


def _handle_lighting(r: _SlowTierResult) -> None:
    r.coordinator.global_lighting_cache[r.cam_id] = (
        r.ep_data if isinstance(r.ep_data, dict) else {}
    )


def _handle_intrusion_detection_config(r: _SlowTierResult) -> None:
    # Skip cache overwrite within the write-lock window — otherwise a
    # slow-tier poll hitting before the cloud has caught up to the user's
    # toggle reverts the switch back to the stale enabled value.
    if not r.coordinator.is_write_locked(
        r.cam_id, r.coordinator.intrusion_config_set_at
    ):
        r.coordinator.intrusion_config_cache[r.cam_id] = (
            r.ep_data if isinstance(r.ep_data, dict) else {}
        )


def _handle_audio_detection_config(r: _SlowTierResult) -> None:
    # Glass-break / fire-alarm sound detection (Gen2 Audio-Plus). Skip
    # cache overwrite within the write-lock window so an optimistic toggle
    # isn't reverted by a slow-tier poll before cloud catches up.
    if not r.coordinator.is_write_locked(
        r.cam_id, r.coordinator.audio_detection_set_at
    ):
        r.coordinator.audio_detection_cache[r.cam_id] = (
            r.ep_data if isinstance(r.ep_data, dict) else {}
        )


def _handle_alarm_settings(r: _SlowTierResult) -> None:
    # Skip within the write-lock window (cloud propagation) so the
    # optimistic cache isn't reverted.
    if not r.coordinator.is_write_locked(r.cam_id, r.coordinator.alarm_settings_set_at):
        r.coordinator.alarm_settings_cache[r.cam_id] = (
            r.ep_data if isinstance(r.ep_data, dict) else {}
        )


def _handle_alarm_status(r: _SlowTierResult) -> None:
    # Actual response format confirmed 2026-04-11:
    #   {"alarmType": "NONE" | ..., "intrusionSystem": "INACTIVE" | "ACTIVE" | ...}
    r.coordinator.alarm_status_cache[r.cam_id] = (
        r.ep_data if isinstance(r.ep_data, dict) else {}
    )
    if isinstance(r.ep_data, dict) and not r.coordinator.is_write_locked(
        r.cam_id, r.coordinator.arming_set_at
    ):
        intrusion = str(r.ep_data.get("intrusionSystem", "")).upper()
        if intrusion == "ACTIVE":
            r.coordinator.arming_cache[r.cam_id] = True
        elif intrusion == "INACTIVE":
            r.coordinator.arming_cache[r.cam_id] = False
    if isinstance(r.ep_data, dict):
        r.fire_intrusion_event(
            r.cam_id,
            r.cam_raw.get("title", r.cam_id),
            r.ep_data,
        )


def _handle_icon_led_brightness(r: _SlowTierResult) -> None:
    # Power-LED brightness 0-4 (5 discrete steps: off + 4 levels)
    try:
        val = int(r.ep_data.get("value", 0)) if isinstance(r.ep_data, dict) else 0
        r.coordinator.icon_led_brightness_cache[r.cam_id] = max(0, min(4, val))
    except TypeError, ValueError:
        r.coordinator.icon_led_brightness_cache[r.cam_id] = 0


def _handle_zones(r: _SlowTierResult) -> None:
    zones_data: list[Any] = r.ep_data if isinstance(r.ep_data, list) else []
    r.coordinator.gen2_zones_cache[r.cam_id] = zones_data
    _LOGGER.debug("Gen2 zones for %s: %d zones fetched", r.cam_id[:8], len(zones_data))


def _handle_private_areas(r: _SlowTierResult) -> None:
    areas_data: list[Any] = r.ep_data if isinstance(r.ep_data, list) else []
    r.coordinator.gen2_private_areas_cache[r.cam_id] = areas_data
    _LOGGER.debug(
        "Gen2 privateAreas for %s: %d areas fetched", r.cam_id[:8], len(areas_data)
    )


_SLOW_TIER_HANDLERS: dict[str, Callable[[_SlowTierResult], None]] = {
    "wifiinfo": _handle_wifiinfo,
    "ambient_light_sensor_level": _handle_ambient_light_sensor_level,
    "motion": _handle_motion,
    "firmware": _handle_firmware,
    "recording_options": _handle_recording_options,
    "unread_events_count": _handle_unread_events_count,
    "privacy_sound_override": _handle_privacy_sound_override,
    "commissioned": _handle_commissioned,
    "autofollow": _handle_autofollow,
    "timestamp": _handle_timestamp,
    "notifications": _handle_notifications,
    "rules": _handle_rules,
    "motion_sensitive_areas": _handle_motion_sensitive_areas,
    "privacy_masks": _handle_privacy_masks,
    "lighting_options": _handle_lighting_options,
    "ledlights": _handle_ledlights,
    "lens_elevation": _handle_lens_elevation,
    "audio": _handle_audio,
    "lighting/motion": _handle_lighting_motion,
    "lighting/ambient": _handle_lighting_ambient,
    "lighting": _handle_lighting,
    "intrusionDetectionConfig": _handle_intrusion_detection_config,
    "audioDetectionConfig": _handle_audio_detection_config,
    "alarm_settings": _handle_alarm_settings,
    "alarmStatus": _handle_alarm_status,
    "iconLedBrightness": _handle_icon_led_brightness,
    "zones": _handle_zones,
    "privateAreas": _handle_private_areas,
}


def _dispatch_slow_tier_result(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    cam_raw: dict[str, Any],
    data: dict[str, Any],
    fire_intrusion_event: Callable[[str, str, dict[str, Any]], None],
    ep: str,
    ep_data: Any,
) -> None:
    """Apply one slow-tier endpoint's 200-OK result to the coordinator's caches."""
    handler = _SLOW_TIER_HANDLERS.get(ep)
    if handler is not None:
        handler(
            _SlowTierResult(
                coordinator, cam_id, cam_raw, data, fire_intrusion_event, ep_data
            )
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
    """Slow-tier (~5-min interval) parallel endpoint fetch + result dispatch.

    Covers wifiinfo, ambient light, motion, firmware, recording
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
    # Reduces slow-tier from ~13x5s = 65s to ~5s (single timeout).
    async def _fetch(
        endpoint: str,
    ) -> tuple[str, int, dict[str, Any] | None]:
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
                err_str(err),
            )
            return (endpoint, 0, None)

    endpoints = _slow_tier_endpoint_list(ctx)
    results = await asyncio.gather(
        *[_fetch(ep) for ep in endpoints],
        return_exceptions=True,
    )

    for fetch_result in results:
        if isinstance(fetch_result, BaseException):
            continue
        ep, ep_status, ep_data = fetch_result
        if ep_status != 200 or ep_data is None:
            continue
        _dispatch_slow_tier_result(
            coordinator, cam_id, cam_raw, data, fire_intrusion_event, ep, ep_data
        )

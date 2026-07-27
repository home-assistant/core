"""Slow-tier per-camera diagnostic pass.

Snapshot-only Core build: the only slow-tier endpoint fetched is
`motion` (motion-detection settings), gated on `ctx.do_slow_cam and
ctx.is_online`. Every other endpoint the pre-Core HACS build polled
(wifiinfo, firmware, zones, alarm status, lighting, rules, etc.) had no
reader anywhere in this reduced camera-platform-only tree and was
removed as dead per-tick cloud traffic (bug-hunt 2026-07-27, Copilot
review) — see `_slow_tier_endpoint_list`/`_SLOW_TIER_HANDLERS` below.
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
    """No-op in this snapshot-only build.

    The original pan-position and Gen2 lighting/switch every-tick fetches
    populated `coordinator.pan_cache`/`lighting_switch_cache`, which have no
    reader anywhere in this camera-only build (no select/number/light
    platforms) — removed to stop making unnecessary cloud requests every
    tick (bug-hunt 2026-07-27, Copilot review). Kept as a function (rather
    than removing the call site in coordinator.py) so re-adding a consumer
    platform later is a one-line revert.
    """


def _slow_tier_endpoint_list(ctx: CamContext) -> list[str]:
    """Build the list of slow-tier endpoints applicable to this camera.

    Trimmed to `motion` only (bug-hunt 2026-07-27, Copilot review): this is
    a camera-only build with no sensor/binary_sensor/switch/light/number/
    select platforms, so wifiinfo/firmware/zones/privacy_masks/rules/
    alarm/lighting/etc. only ever populated a coordinator cache dict with no
    reader anywhere — 10-28 unnecessary cloud requests per camera every
    five minutes. `motion` is the one real exception: it feeds
    `data[cam_id]["motion"]`, read by `coordinator.motion_settings()` for
    the standard HA `camera.enable/disable_motion_detection` services.
    """
    del ctx  # unused now that the list no longer varies by hardware generation
    return ["motion"]


@dataclass
class _SlowTierResult:
    """Bundles everything a single-endpoint handler needs."""

    coordinator: BoschCameraCoordinator
    cam_id: str
    cam_raw: dict[str, Any]
    data: dict[str, Any]
    ep_data: Any


def _handle_motion(r: _SlowTierResult) -> None:
    # Skip within the write-lock window so a poll that lands before the
    # cloud reflects the user's sensitivity change doesn't revert the UI.
    if not r.coordinator.is_write_locked(r.cam_id, r.coordinator.motion_set_at):
        r.data[r.cam_id]["motion"] = r.ep_data


_SLOW_TIER_HANDLERS: dict[str, Callable[[_SlowTierResult], None]] = {
    "motion": _handle_motion,
}


def _dispatch_slow_tier_result(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    cam_raw: dict[str, Any],
    data: dict[str, Any],
    ep: str,
    ep_data: Any,
) -> None:
    """Apply one slow-tier endpoint's 200-OK result to the coordinator's caches."""
    handler = _SLOW_TIER_HANDLERS.get(ep)
    if handler is not None:
        handler(_SlowTierResult(coordinator, cam_id, cam_raw, data, ep_data))


async def _poll_slow_tier_endpoints(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    cam_raw: dict[str, Any],
    ctx: CamContext,
    data: dict[str, Any],
    session: aiohttp.ClientSession,
    headers: dict[str, str],
) -> None:
    """Slow-tier (~5-min interval) endpoint fetch + result dispatch.

    Only fetches `motion` in this camera-only build (see
    `_slow_tier_endpoint_list`'s docstring) — kept structured as a
    parallel-fetch-then-dispatch pass rather than inlined so re-adding a
    consumer platform later only needs a new handler + endpoint-list entry.

    Only runs when `ctx.do_slow_cam and ctx.is_online` (skipped when
    camera is offline or session-quota hit — endpoints would return
    444 too, and the camera isn't truly unreachable).
    """
    if not (ctx.do_slow_cam and ctx.is_online):
        return

    # ── Slow-tier fetch ──────────────────────────────
    # Single-endpoint today (see _slow_tier_endpoint_list), but fetched via
    # asyncio.gather() over the endpoint list rather than a bespoke
    # single-request call so re-adding endpoints later doesn't need to
    # rebuild the parallel-fetch machinery.
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
        _dispatch_slow_tier_result(coordinator, cam_id, cam_raw, data, ep, ep_data)

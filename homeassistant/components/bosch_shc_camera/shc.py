"""SHC local API and Cloud API setter functions for Bosch Smart Home cameras.

Extracted from the coordinator class to keep __init__.py focused on
polling / data merging. Every function below receives the coordinator
instance as its first argument instead of using `self`. `SHCCoordinatorMixin`
at the end of this file is the exception — it's mixed into
BoschCameraCoordinator (see __init__.py's class declaration) and its methods
DO use `self`, but each one is just a one-line delegator back to the
free function of the same purpose above (same pattern as FCMCoordinatorMixin
in fcm.py / FrigateCoordinatorMixin in frigate_endpoint.py).

Public API (cloud setters — used by switch / number entities):
  async_cloud_set_privacy_mode(coordinator, cam_id, enabled)
  async_cloud_set_camera_light(coordinator, cam_id, on)
  async_cloud_set_light_component(coordinator, cam_id, component, value)
  async_cloud_set_notifications(coordinator, cam_id, enabled)
  async_cloud_set_pan(coordinator, cam_id, position)

SHC-only setters (used as fallback by the cloud setters above):
  async_shc_set_camera_light(coordinator, cam_id, on)
  async_shc_set_privacy_mode(coordinator, cam_id, enabled)

Low-level helpers:
  shc_configured(coordinator) -> bool
  shc_ready(coordinator) -> bool
  async_shc_request(coordinator, method, path, body) -> dict | list | None
  async_update_shc_states(coordinator, data) -> None
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import time
from typing import TYPE_CHECKING, Any

import aiohttp
from bosch_shc_camera_client.cloud import cloud_put_json

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import UpdateFailed

from .cloud_ssl import async_get_bosch_cloud_session

if TYPE_CHECKING:
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)

CLOUD_API = "https://residential.cbs.boschsecurity.com"

# SSLContext is stateless after init — safe to cache and share across requests
_SHC_SSL_CONTEXTS: dict[tuple[str, str], ssl.SSLContext] = {}


def _get_shc_ssl_ctx(cert_path: str, key_path: str) -> ssl.SSLContext:
    key = (cert_path, key_path)
    if key not in _SHC_SSL_CONTEXTS:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.load_cert_chain(cert_path, key_path)  # may raise; not cached on failure
        _SHC_SSL_CONTEXTS[key] = ctx
    return _SHC_SSL_CONTEXTS[key]


# ── SHC availability helpers ────────────────────────────────────────────────


def shc_configured(coordinator: BoschCameraCoordinator) -> bool:
    """True if SHC local API is fully configured (IP + certs)."""
    opts = coordinator.options
    return bool(
        opts.get("shc_ip", "").strip()
        and opts.get("shc_cert_path", "").strip()
        and opts.get("shc_key_path", "").strip()
    )


def shc_ready(coordinator: BoschCameraCoordinator) -> bool:
    """True if SHC is configured AND currently considered available.

    When SHC is offline (too many consecutive failures), returns False
    unless the retry interval has elapsed.
    """
    if not shc_configured(coordinator):
        return False
    if coordinator.shc_available:
        return True
    # SHC is offline -- check if retry interval has passed
    now = time.monotonic()
    if now - coordinator.shc_last_check >= coordinator.SHC_RETRY_INTERVAL:
        return True  # allow one retry
    return False


def _shc_mark_success(coordinator: BoschCameraCoordinator) -> None:
    """Mark SHC as healthy after a successful request."""
    if not coordinator.shc_available:
        _LOGGER.info("SHC local API is back online")
    coordinator.shc_available = True
    coordinator.shc_fail_count = 0


def _shc_mark_failure(coordinator: BoschCameraCoordinator) -> None:
    """Track a failed SHC request; mark offline after N consecutive failures."""
    coordinator.shc_fail_count += 1
    if (
        coordinator.shc_fail_count >= coordinator.SHC_MAX_FAILS
        and coordinator.shc_available
    ):
        coordinator.shc_available = False
        coordinator.shc_last_check = time.monotonic()
        _LOGGER.warning(
            "SHC local API marked offline after %d consecutive failures -- "
            "will retry in %ds. Falling back to cloud API.",
            coordinator.shc_fail_count,
            coordinator.SHC_RETRY_INTERVAL,
        )


# ── SHC low-level request ───────────────────────────────────────────────────


async def async_shc_request(
    coordinator: BoschCameraCoordinator,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
) -> dict[Any, Any] | list[Any] | None:
    """Make a request to the SHC local API using mutual TLS.

    Returns parsed JSON on success, None on failure.
    Requires shc_ip, shc_cert_path, shc_key_path in options.
    Tracks SHC health -- marks offline after repeated failures.
    """
    opts = coordinator.options
    shc_ip = opts.get("shc_ip", "").strip()
    cert_path = opts.get("shc_cert_path", "").strip()
    key_path = opts.get("shc_key_path", "").strip()
    if not shc_ip or not cert_path or not key_path:
        return None

    try:
        ctx = _get_shc_ssl_ctx(cert_path, key_path)
    except OSError as err:
        _LOGGER.warning("SHC TLS setup failed (check cert/key paths): %s", err)
        _SHC_SSL_CONTEXTS.pop((cert_path, key_path), None)
        _shc_mark_failure(coordinator)
        return None

    # Reuse connector across calls — avoids a new TLS handshake per request
    _connector_key = (cert_path, key_path)
    _cached_conn: aiohttp.TCPConnector | None = getattr(
        coordinator, "shc_connector", None
    )
    if (
        _cached_conn is None
        or _cached_conn.closed
        or getattr(coordinator, "shc_connector_key", None) != _connector_key
    ):
        _cached_conn = aiohttp.TCPConnector(ssl=ctx)
        coordinator.shc_connector = _cached_conn
        coordinator.shc_connector_key = _connector_key

    url = f"https://{shc_ip}:8444/smarthome{path}"
    headers = {"api-version": "3.2", "Content-Type": "application/json"}
    try:
        async with aiohttp.ClientSession(
            connector=_cached_conn, connector_owner=False
        ) as s:
            async with asyncio.timeout(10):
                if method == "GET":
                    async with s.get(url, headers=headers) as r:
                        if r.status == 200:
                            _shc_mark_success(coordinator)
                            return await r.json()  # type: ignore[no-any-return]
                        _LOGGER.debug("SHC GET %s -> HTTP %d", path, r.status)
                        _shc_mark_failure(coordinator)
                elif method == "PUT":
                    async with s.put(url, json=body, headers=headers) as r:
                        _LOGGER.debug("SHC PUT %s -> HTTP %d", path, r.status)
                        if r.status in (200, 201, 204):
                            _shc_mark_success(coordinator)
                        else:
                            _shc_mark_failure(coordinator)
                        return {"status": r.status, "ok": r.status in (200, 201, 204)}
    except TimeoutError:
        _LOGGER.debug("SHC request timeout: %s %s", method, path)
        _shc_mark_failure(coordinator)
    except aiohttp.ClientError as err:
        _LOGGER.debug("SHC request error %s %s: %s", method, path, err)
        _shc_mark_failure(coordinator)
    except ValueError as err:
        # r.json() raises json.JSONDecodeError (a ValueError) on a malformed
        # body; aiohttp's own content-type mismatch is already aiohttp.ClientError above.
        _LOGGER.debug("SHC unexpected error %s %s: %s", method, path, err)
        _shc_mark_failure(coordinator)
    return None


# ── SHC state polling ────────────────────────────────────────────────────────


async def _update_one_camera_shc_state(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    cam: dict[str, Any],
    shc_devices: list[dict[str, Any]],
) -> None:
    """Fetch and cache SHC CameraLight + PrivacyMode state for a single camera."""
    title = cam.get("info", {}).get("title", "").lower().strip()

    device_id = None
    for dev in shc_devices:
        if dev.get("name", "").lower().strip() == title:
            device_id = dev.get("id")
            break
    if not device_id:
        _LOGGER.debug("SHC: no device found matching camera title '%s'", title)
        return

    entry = coordinator.shc_state_cache.setdefault(
        cam_id,
        {
            "device_id": device_id,
            "camera_light": None,
            "privacy_mode": None,
        },
    )
    entry["device_id"] = device_id

    # Fetch CameraLight service state (SHC is authoritative)
    svc = await async_shc_request(
        coordinator, "GET", f"/devices/{device_id}/services/CameraLight"
    )
    if isinstance(svc, dict):
        val = svc.get("state", {}).get("value", "")
        new_light = val.upper() == "ON"
        # Honor _light_set_at write-lock — same race as privacy_mode.
        # Without this, a fresh user-toggle can be overwritten by a
        # stale SHC reading within the cloud's eventual-consistency
        # window. Fixed 2026-05-05.
        light_lock = coordinator.light_set_at.get(cam_id)
        ttl = getattr(coordinator, "WRITE_LOCK_SECS", 0)
        light_locked = light_lock is not None and (time.monotonic() - light_lock) < ttl
        old_light = entry.get("camera_light")
        if light_locked and old_light is not None and old_light != new_light:
            _LOGGER.debug(
                "camera_light write-lock active for %s — keeping cached "
                "%s, ignoring SHC value %s",
                cam_id[:8],
                old_light,
                new_light,
            )
        else:
            entry["camera_light"] = new_light

    # Fetch PrivacyMode service state (SHC is authoritative)
    svc = await async_shc_request(
        coordinator, "GET", f"/devices/{device_id}/services/PrivacyMode"
    )
    if isinstance(svc, dict):
        val = svc.get("state", {}).get("value", "")
        new_priv = val.upper() == "ENABLED"
        # Honor the _privacy_set_at write-lock (same pattern that
        # __init__.py:1690 already respects for the cloud fetcher).
        # Without this guard the SHC fetcher overwrites a fresh
        # user-toggle within the cloud's eventual-consistency window
        # → first OFF-toggle visibly reverts to ON until the next
        # user click forces the issue. Fixed 2026-05-05.
        lock_ts = coordinator.privacy_set_at.get(cam_id)
        ttl = getattr(coordinator, "WRITE_LOCK_SECS", 0)
        locked = lock_ts is not None and (time.monotonic() - lock_ts) < ttl
        old_priv = entry.get("privacy_mode")
        if locked and old_priv is not None and old_priv != new_priv:
            _LOGGER.debug(
                "privacy_mode write-lock active for %s — keeping cached "
                "value %s, ignoring SHC value %s (lock_age=%.1fs ttl=%.1fs)",
                cam_id[:8],
                old_priv,
                new_priv,
                time.monotonic() - lock_ts if lock_ts is not None else 0.0,
                ttl,
            )
        else:
            entry["privacy_mode"] = new_priv


async def async_update_shc_states(
    coordinator: BoschCameraCoordinator, data: dict[str, Any]
) -> None:
    """Fetch CameraLight and PrivacyMode states from SHC for each camera.

    SHC is the PRIMARY source for privacy + light state when configured.
    Values from SHC overwrite any cloud-sourced values from step 4.
    Matches SHC devices to cloud cameras by device name (title).
    Refreshes the SHC device list at most once per 60 seconds.
    """
    if not shc_configured(coordinator):
        return

    # Re-fetch device list at most once per 60 s
    now = time.monotonic()
    if now - coordinator.last_shc_fetch >= 60 or not coordinator.shc_devices_raw:
        devices = await async_shc_request(coordinator, "GET", "/devices")
        if isinstance(devices, list):
            coordinator.shc_devices_raw = devices
            coordinator.last_shc_fetch = now

    shc_devices = coordinator.shc_devices_raw
    if not shc_devices:
        return

    await asyncio.gather(
        *[
            _update_one_camera_shc_state(coordinator, cam_id, cam, shc_devices)
            for cam_id, cam in data.items()
        ]
    )


# ── SHC setters ──────────────────────────────────────────────────────────────


async def async_shc_set_camera_light(
    coordinator: BoschCameraCoordinator, cam_id: str, on: bool
) -> bool:
    """Turn the camera indicator LED on (True) or off (False) via SHC API."""
    device_id = coordinator.shc_state_cache.get(cam_id, {}).get("device_id")
    if not device_id:
        # Expected on cold start before the first SHC poll populates the cache;
        # the next coordinator tick fixes it → DEBUG, not WARNING.
        _LOGGER.debug("SHC: no device_id cached for %s -- cannot control light", cam_id)
        return False
    result = await async_shc_request(
        coordinator,
        "PUT",
        f"/devices/{device_id}/services/CameraLight/state",
        {"@type": "cameraLightState", "value": "ON" if on else "OFF"},
    )
    if (
        result
        and isinstance(result, dict)
        and result.get("ok", result.get("status", 0) in (200, 201, 204))
    ):
        coordinator.shc_state_cache[cam_id]["camera_light"] = on
        coordinator.async_update_listeners()
        # No forced refresh — optimistic cache + listeners above suffice; regular tick confirms. Avoids re-registering go2rtc / disrupting unrelated live streams (path C, 2026-05-29).
        return True
    return False


async def async_shc_set_privacy_mode(
    coordinator: BoschCameraCoordinator, cam_id: str, enabled: bool
) -> bool:
    """Enable (True) or disable (False) privacy mode via SHC API (legacy fallback)."""
    device_id = coordinator.shc_state_cache.get(cam_id, {}).get("device_id")
    if not device_id:
        # Expected on cold start before the first SHC poll populates the cache;
        # the next coordinator tick fixes it → DEBUG, not WARNING.
        _LOGGER.debug(
            "SHC: no device_id cached for %s -- cannot set privacy mode", cam_id
        )
        return False
    result = await async_shc_request(
        coordinator,
        "PUT",
        f"/devices/{device_id}/services/PrivacyMode/state",
        {"@type": "privacyModeState", "value": "ENABLED" if enabled else "DISABLED"},
    )
    if (
        result
        and isinstance(result, dict)
        and result.get("ok", result.get("status", 0) in (200, 201, 204))
    ):
        coordinator.shc_state_cache[cam_id]["privacy_mode"] = enabled
        coordinator.privacy_set_at[cam_id] = time.monotonic()
        coordinator.async_update_listeners()
        # No forced refresh — see async_cloud_set_privacy_mode (path C,
        # 2026-05-29): a privacy toggle must not re-register go2rtc streams and
        # tear down unrelated cameras' live sessions. Optimistic push above +
        # the regular tick are sufficient; privacy-OFF still snapshots below.
        if not enabled:
            _schedule_privacy_off_snapshot(coordinator, cam_id)
        return True
    return False


def _schedule_privacy_off_snapshot(
    coordinator: BoschCameraCoordinator, cam_id: str
) -> None:
    """Trigger a fresh snapshot after privacy mode was disabled.

    Delay depends on the camera's hardware:
    - **Outdoor cameras** (no physical shutter, instant-on): 0.5s — just enough
      for the cloud API to propagate the privacy-off state so /snap.jpg returns
      a fresh frame instead of the privacy placeholder.
    - **Indoor cameras** (physical motor-driven shutter + lens cover): 5.0s —
      Gen1 360 motor-drives the lens upward, Gen2 Indoor II tilts the head.
      Snap.jpg returns the privacy placeholder until the shutter fully opens
      AND the encoder produces a valid frame. User-observed: 4s occasionally
      returned a placeholder frame for Gen2 Indoor II that bytes-matched the
      next poll, stalling the card spinner on the old image; 5s covers the
      slowest observed shutter-open + encoder-ready cycle.
    """
    cam = coordinator.camera_entities.get(cam_id)
    if not cam:
        return
    hw = coordinator.hw_version.get(cam_id, "")
    hw_lower = hw.lower()
    is_indoor = (
        hw in ("INDOOR", "CAMERA_360", "HOME_Eyes_Indoor", "CAMERA_INDOOR_GEN2")
        or "indoor" in hw_lower
        or "360" in hw_lower
    )
    delay = 5.0 if is_indoor else 0.5
    _LOGGER.debug(
        "Privacy-OFF snapshot trigger for %s (hw=%s, delay=%.1fs)",
        cam_id[:8],
        hw,
        delay,
    )
    coordinator.hass.async_create_task(cam.async_trigger_image_refresh(delay=delay))


# ── Cloud API setters ────────────────────────────────────────────────────────


async def _notify_write_failed(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    feature_key: str,
    feature_label: str,
    desired_label: str,
) -> None:
    """Best-effort persistent_notification when every write path is exhausted.

    Fires unconditionally — not gated on `_auth_outage_count` (that counter
    only tracks consecutive 5xx from the coordinator's own *polling* loop, so
    a one-off write-time failure while a user is toggling a switch never
    touches it). Without this, a total failure left zero user-visible
    feedback: the entity just silently reverted, looking like "the button
    does nothing" (live report 2026-07-07, privacy mode; same gap existed —
    even worse, with no notification code path at all — for camera light and
    notifications).

    `notification_id` is deterministic per camera+feature, so repeated
    failures during a real outage overwrite the same entry instead of
    spamming.
    """
    try:
        await coordinator.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": f"Bosch Kamera — {feature_label}-Befehl nicht zugestellt",
                "message": (
                    f"{feature_label} {desired_label} für `{cam_id[:8]}…` konnte "
                    "nicht gesetzt werden: Bosch-Cloud nicht erreichbar und "
                    "lokaler Fallback fehlgeschlagen.\n\n"
                    "Sobald die Cloud wieder online ist, bitte erneut schalten."
                ),
                "notification_id": f"bosch_{feature_key}_queued_{cam_id[:8]}",
            },
        )
    except Exception:  # noqa: BLE001 — best-effort persistent_notification; HA service call non-critical after all write paths exhausted
        pass


async def async_cloud_set_privacy_mode(
    coordinator: BoschCameraCoordinator, cam_id: str, enabled: bool
) -> bool:
    """Enable (True) or disable (False) privacy mode.

    Strategy: Cloud API first (~150ms), SHC local API fallback (~1100ms).
    Cloud is 10x faster due to connection pooling; SHC requires fresh mTLS
    handshake per request on an embedded controller.
    SHC fallback ensures control when cloud is unreachable (offline mode).
    """
    # Skip cloud for known-offline cams: Bosch closes with HTTP 444 → log spam.
    # Also skip for a short window after a recent 444 (cloud session quota / a
    # freshly re-paired camera that is "online" for status but rejects writes) so
    # we go straight to the LAN/SHC fallback instead of re-hitting the cloud for
    # another 444. -inf = never (SENTINEL_RULE).
    _CLOUD_444_COOLDOWN = 120
    cloud_444_at = getattr(coordinator, "cloud_444_at", {})
    _recent_444 = (
        cloud_444_at.get(cam_id, float("-inf")) > time.monotonic() - _CLOUD_444_COOLDOWN
    )
    cam_offline = coordinator.cached_status.get(cam_id) == "OFFLINE" or _recent_444
    if cam_offline:
        _LOGGER.debug(
            "cloud_set_privacy_mode: cam %s offline/cloud-degraded — skipping "
            "cloud, trying fallbacks",
            cam_id,
        )

    # -- Cloud API (primary -- fast) -------------------------------------------
    token = coordinator.token
    if token and not cam_offline:
        session = await async_get_bosch_cloud_session(coordinator.hass)
        url = f"{CLOUD_API}/v11/video_inputs/{cam_id}/privacy"
        body = {"privacyMode": "ON" if enabled else "OFF", "durationInSeconds": None}

        result = await cloud_put_json(session, token, url, body)
        if result.ok:
            # Stamp the write-lock BEFORE updating the cache so the
            # SHC background tick can never see a window where the
            # cache was changed but _privacy_set_at is still unset
            # (the race that caused the first OFF-toggle to revert).
            coordinator.privacy_set_at[cam_id] = time.monotonic()
            coordinator.shc_state_cache.setdefault(cam_id, {})["privacy_mode"] = enabled
            coordinator.async_update_listeners()
            _LOGGER.debug(
                "cloud_set_privacy_mode: %s -> %s (HTTP %d)",
                cam_id,
                "ON" if enabled else "OFF",
                result.status,
            )
            # NO async_request_refresh() here. The cache + listeners
            # above already push the new privacy state to the UI
            # optimistically. A forced (un-throttled) coordinator
            # refresh re-touches go2rtc stream registration for ALL
            # active cameras, which made go2rtc TEARDOWN + reconnect
            # an UNRELATED camera's live session (~1 s blip → "HLS
            # reload" overlay). Incident 2026-05-29, path C. The
            # regular 60 s tick confirms the state; privacy-OFF still
            # triggers a lightweight snapshot refresh below.
            if not enabled:
                _schedule_privacy_off_snapshot(coordinator, cam_id)
            return True

        if result.status == 401:
            # Token expired -- refresh and retry once
            _LOGGER.info("cloud_set_privacy_mode: 401 -- refreshing token and retrying")
            try:
                token = await coordinator.ensure_valid_token(token)
            except (
                ConfigEntryAuthFailed,
                UpdateFailed,
            ):  # token refresh failed; fall through to local SHC path
                pass  # fall through to SHC
            else:
                retry_result = await cloud_put_json(session, token, url, body)
                if retry_result.ok:
                    coordinator.privacy_set_at[cam_id] = time.monotonic()
                    coordinator.shc_state_cache.setdefault(cam_id, {})[
                        "privacy_mode"
                    ] = enabled
                    coordinator.async_update_listeners()
                    # See primary path above: no forced refresh
                    # (path C — avoids tearing down unrelated
                    # cameras' live sessions). 2026-05-29.
                    if not enabled:
                        _schedule_privacy_off_snapshot(coordinator, cam_id)
                    return True

        if result.status == 444 and hasattr(coordinator, "cloud_444_at"):
            # Session quota / not-ready — remember so the next write
            # skips the cloud and uses the LAN/SHC fallback directly.
            coordinator.cloud_444_at[cam_id] = time.monotonic()
        if result.status is not None:
            _LOGGER.warning(
                "cloud_set_privacy_mode: HTTP %d for %s", result.status, cam_id
            )

    # -- Gen2 LOCAL RCP fallback (cloud outage) --------------------------------
    # When the Bosch cloud (auth server or API) is unreachable, Gen2 cameras
    # still answer authenticated RCP commands on their LAN IP via HTTPS+Digest.
    # Try this before SHC — LOCAL RCP works directly against the camera
    # without any Bosch infrastructure involved.
    #
    # Gate: confirmed Gen2 OR unknown (cold-start cloud-outage). Gen1 known →
    # skip (no rcp.xml endpoint). For unknown, the write either succeeds
    # (Gen2) or fails cleanly (Gen1) — same shape as if we'd known.
    _hw = coordinator.hw_version.get(cam_id)
    _gen2_or_unknown = _is_gen2(coordinator, cam_id) or _hw in (None, "", "CAMERA")
    if _gen2_or_unknown:
        creds = coordinator.local_creds_cache.get(cam_id)
        cam_host = (
            creds.get("host") if creds else coordinator.rcp_lan_ip_cache.get(cam_id)
        )
        # Pass cycling LOCAL Digest creds — `rcp.xml` runs HTTPS-only and
        # requires Digest auth on Gen2. Falls through to anonymous mode if
        # no creds are cached (will fail with HTTP 401, surfaced as False).
        local_user = creds.get("user") if creds else None
        local_pass = creds.get("password") if creds else None
        if cam_host:
            from bosch_shc_camera_client.rcp import rcp_local_write_privacy

            local_session = async_get_clientsession(coordinator.hass, verify_ssl=False)
            ok = await rcp_local_write_privacy(
                local_session,
                cam_host,
                enabled,
                user=local_user,
                password=local_pass,
            )
            if ok:
                _LOGGER.info(
                    "cloud_set_privacy_mode: cloud failed, Gen2 LOCAL RCP succeeded for %s",
                    cam_id,
                )
                _now = time.monotonic()
                coordinator.privacy_set_at[cam_id] = _now
                # Local RCP writes briefly tear down the camera's cloud TLS
                # session as Digest creds rotate. Record the timestamp so
                # `is_lan_reachable()` masks transient ping failures in the
                # ~30 s window after the write.
                if hasattr(coordinator, "local_write_at"):
                    coordinator.local_write_at[cam_id] = _now
                coordinator.shc_state_cache.setdefault(cam_id, {})["privacy_mode"] = (
                    enabled
                )
                coordinator.async_update_listeners()
                return True
            _LOGGER.debug(
                "cloud_set_privacy_mode: Gen2 LOCAL RCP fallback failed for %s — "
                "camera may not accept unauthenticated writes",
                cam_id,
            )

    # -- SHC local API fallback (offline mode) ---------------------------------
    if shc_ready(coordinator):
        _LOGGER.info(
            "cloud_set_privacy_mode: cloud failed, falling back to SHC for %s", cam_id
        )
        if await async_shc_set_privacy_mode(coordinator, cam_id, enabled):
            return True
        # SHC was reachable but its own write also failed (e.g. no cached
        # device_id yet, or a non-2xx from the local PUT) — fall through to
        # the notification tail instead of returning this False directly.
        # Returning early here reproduced the exact "swallowed failure" bug
        # this function was fixed for, just for this one sub-case (found by
        # bug-hunt verification, 2026-07-07).

    # -- All fallbacks exhausted — surface a persistent notification ----------
    await _notify_write_failed(
        coordinator, cam_id, "privacy", "Privacy-Mode", "ON" if enabled else "OFF"
    )
    return False


def _is_gen2(coordinator: BoschCameraCoordinator, cam_id: str) -> bool:
    """Check if a camera is Gen2 (uses different lighting endpoints)."""
    from .models import get_model_config

    hw = coordinator.hw_version.get(cam_id, "CAMERA")
    return get_model_config(hw).generation >= 2


async def async_cloud_set_camera_light(
    coordinator: BoschCameraCoordinator, cam_id: str, on: bool
) -> bool:
    """Turn the camera light on (True) or off (False).

    Strategy: Cloud API first (~150ms), SHC local API fallback (~1100ms).
    Gen1: PUT /lighting_override with frontLightOn + wallwasherOn
    Gen2: PUT /lighting/switch/front + /lighting/switch/topdown with enabled
    """
    # -- Cloud API (primary -- fast) -------------------------------------------
    token = coordinator.token
    if token:
        session = await async_get_bosch_cloud_session(coordinator.hass)
        gen2 = _is_gen2(coordinator, cam_id)
        ok = False

        if gen2:
            # Gen2: separate endpoints for front and top-down lights
            base = f"{CLOUD_API}/v11/video_inputs/{cam_id}/lighting/switch"
            body_toggle = {"enabled": on}
            r1 = await cloud_put_json(session, token, f"{base}/front", body_toggle)
            r2 = await cloud_put_json(session, token, f"{base}/topdown", body_toggle)
            ok = r1.ok or r2.ok
            if not ok:
                _LOGGER.warning(
                    "cloud_set_camera_light (gen2): front=%s topdown=%s for %s",
                    r1.status,
                    r2.status,
                    cam_id,
                )
        else:
            # Gen1: single endpoint with combined body
            url = f"{CLOUD_API}/v11/video_inputs/{cam_id}/lighting_override"
            cache = coordinator.shc_state_cache.get(cam_id, {})
            last_intensity = cache.get("front_light_intensity") or 1.0
            if on:
                body = {
                    "frontLightOn": True,
                    "wallwasherOn": True,
                    "frontLightIntensity": last_intensity,
                }
            else:
                body = {"frontLightOn": False, "wallwasherOn": False}
            result = await cloud_put_json(session, token, url, body)
            ok = result.ok
            if not ok:
                _LOGGER.warning(
                    "cloud_set_camera_light: HTTP %s for %s", result.status, cam_id
                )

        if ok:
            cache_entry = coordinator.shc_state_cache.setdefault(cam_id, {})
            cache_entry["camera_light"] = on
            cache_entry["front_light"] = on
            cache_entry["wallwasher"] = on
            coordinator.light_set_at[cam_id] = time.monotonic()
            coordinator.async_update_listeners()
            _LOGGER.debug(
                "cloud_set_camera_light: %s -> %s (gen%d)",
                cam_id[:8],
                "ON" if on else "OFF",
                2 if gen2 else 1,
            )
            # No forced refresh — optimistic cache + listeners above suffice; regular tick confirms. Avoids re-registering go2rtc / disrupting unrelated live streams (path C, 2026-05-29).
            return True

    # -- SHC local API fallback (offline mode) ---------------------------------
    if shc_ready(coordinator):
        _LOGGER.info(
            "cloud_set_camera_light: cloud failed, falling back to SHC for %s", cam_id
        )
        if await async_shc_set_camera_light(coordinator, cam_id, on):
            return True
        # SHC was reachable but its own write also failed — fall through to
        # the notification tail (same fix as async_cloud_set_privacy_mode,
        # found by bug-hunt verification 2026-07-07).
    await _notify_write_failed(
        coordinator, cam_id, "light", "Kameralicht", "ON" if on else "OFF"
    )
    return False


async def async_cloud_set_light_component(
    coordinator: BoschCameraCoordinator, cam_id: str, component: str, value: Any
) -> bool:
    """Set individual light component.

    Gen1: PUT /v11/video_inputs/{id}/lighting_override
      component: "front" (bool), "wallwasher" (bool), or "intensity" (float 0.0-1.0).
    Gen2: PUT /v11/video_inputs/{id}/lighting/switch/front or /topdown
      component: "front" (bool), "wallwasher" (bool), or "intensity" (int 0-100).
    """
    token = coordinator.token
    # Session is only created when we have a token to use it with. The Gen2
    # LAN-RCP fallback at the end of this function works without a cloud
    # session, so we skip the (sometimes expensive) session+resolver setup
    # entirely when token is missing. Type guard before each cloud_put_json call.
    session = await async_get_bosch_cloud_session(coordinator.hass) if token else None
    cache = coordinator.shc_state_cache.get(cam_id, {})
    gen2 = _is_gen2(coordinator, cam_id)
    ok = False

    if gen2 and token:
        # Gen2: separate endpoints per light group
        base = f"{CLOUD_API}/v11/video_inputs/{cam_id}/lighting/switch"
        if component == "front":
            url = f"{base}/front"
            body = {"enabled": value}
        elif component == "wallwasher":
            # Wallwasher controls BOTH top + bottom LEDs.
            # Must sync brightness via /lighting/switch AND toggle via /topdown
            # to keep light entities and wallwasher switch in sync.
            lsc = coordinator.lighting_switch_cache.get(cam_id, {})
            front_settings = lsc.get(
                "frontLightSettings",
                {"brightness": 0, "color": None, "whiteBalance": -1.0},
            )
            if not hasattr(coordinator, "last_topdown_brightness"):
                coordinator.last_topdown_brightness = {}
            if value:
                # Turn ON: restore last brightness, then enable topdown
                saved = coordinator.last_topdown_brightness.get(cam_id, {})
                top_bri = saved.get("top", 100)
                bot_bri = saved.get("bottom", 100)
                top_settings = {
                    **lsc.get(
                        "topLedLightSettings", {"color": None, "whiteBalance": -1.0}
                    ),
                    "brightness": top_bri,
                }
                bot_settings = {
                    **lsc.get(
                        "bottomLedLightSettings", {"color": None, "whiteBalance": -1.0}
                    ),
                    "brightness": bot_bri,
                }
            else:
                # Turn OFF: save current brightness, then zero it
                cur_top = lsc.get("topLedLightSettings", {}).get("brightness", 0)
                cur_bot = lsc.get("bottomLedLightSettings", {}).get("brightness", 0)
                if cur_top > 0 or cur_bot > 0:
                    coordinator.last_topdown_brightness[cam_id] = {
                        "top": cur_top or 100,
                        "bottom": cur_bot or 100,
                    }
                top_settings = {
                    **lsc.get(
                        "topLedLightSettings", {"color": None, "whiteBalance": -1.0}
                    ),
                    "brightness": 0,
                }
                bot_settings = {
                    **lsc.get(
                        "bottomLedLightSettings", {"color": None, "whiteBalance": -1.0}
                    ),
                    "brightness": 0,
                }
            full_body = {
                "frontLightSettings": front_settings,
                "topLedLightSettings": top_settings,
                "bottomLedLightSettings": bot_settings,
            }
            # Step 1: Set brightness via /lighting/switch
            assert session is not None  # narrowed by `if gen2 and token` above
            step1 = await cloud_put_json(session, token, base, full_body)
            if step1.ok:
                coordinator.lighting_switch_cache[cam_id] = (
                    step1.body if step1.body is not None else full_body
                )
            else:
                _LOGGER.warning(
                    "cloud_set_light_component (gen2): lighting/switch HTTP %s for %s",
                    step1.status,
                    cam_id[:8],
                )
            # Step 2: Toggle topdown switch
            url = f"{base}/topdown"
            body = {"enabled": value}
        elif component == "intensity":
            # Gen2 brightness is 0-100 (Gen1 is 0.0-1.0)
            brightness = (
                int(value * 100)
                if isinstance(value, float) and value <= 1.0
                else int(value)
            )
            url = base
            body = {
                "frontLightSettings": {
                    "brightness": brightness,
                    "whiteBalance": -1.0,
                    "color": None,
                },
                "topLedLightSettings": {
                    "brightness": brightness,
                    "whiteBalance": -1.0,
                    "color": None,
                },
                "bottomLedLightSettings": {
                    "brightness": brightness,
                    "whiteBalance": -1.0,
                    "color": None,
                },
            }
        else:
            return False
        assert session is not None  # narrowed by `if gen2 and token` above
        result = await cloud_put_json(session, token, url, body)
        ok = result.ok
        if not ok:
            _LOGGER.warning(
                "cloud_set_light_component (gen2): HTTP %s for %s %s",
                result.status,
                cam_id[:8],
                component,
            )
    elif not gen2 and token:
        # Gen1: single endpoint with combined body
        front = cache.get("front_light") or False
        wall = cache.get("wallwasher") or False
        intensity = cache.get("front_light_intensity") or 1.0

        if component == "front":
            front = value
        elif component == "wallwasher":
            wall = value
        elif component == "intensity":
            intensity = value

        # Bosch API constraint (verified live 2026-04-25): the lighting_override
        # endpoint rejects frontLightIntensity if frontLightOn is False with HTTP 400
        # `frontIlluminatorIntensity must not be set if frontLightOn is false`. Omit
        # the intensity field when the front light is being turned off.
        body = {"frontLightOn": front, "wallwasherOn": wall}
        if front:
            body["frontLightIntensity"] = intensity
        url = f"{CLOUD_API}/v11/video_inputs/{cam_id}/lighting_override"
        assert session is not None  # narrowed by `elif not gen2 and token` above
        result = await cloud_put_json(session, token, url, body)
        ok = result.ok
        if not ok:
            _LOGGER.warning(
                "cloud_set_light_component: HTTP %s for %s — body sent=%s, response=%s",
                result.status,
                cam_id,
                body,
                (result.text or "")[:200],
            )

    if ok:
        cache_entry = coordinator.shc_state_cache.setdefault(cam_id, {})
        if component == "front":
            cache_entry["front_light"] = value
        elif component == "wallwasher":
            cache_entry["wallwasher"] = value
        elif component == "intensity":
            cache_entry["front_light_intensity"] = value
        cache_entry["camera_light"] = cache_entry.get("front_light") or cache_entry.get(
            "wallwasher"
        )
        coordinator.light_set_at[cam_id] = time.monotonic()
        coordinator.async_update_listeners()
        _LOGGER.debug(
            "cloud_set_light_component: %s %s=%s (gen%d)",
            cam_id[:8],
            component,
            value,
            2 if gen2 else 1,
        )
        # No forced refresh — optimistic cache + listeners above suffice; regular tick confirms. Avoids re-registering go2rtc / disrupting unrelated live streams (path C, 2026-05-29).
        return True

    # -- Gen2 LOCAL RCP fallback for front-light (cloud outage) ---------------
    # Mirror of the privacy fallback. Only supports "front" + "intensity" —
    # wallwasher RGB needs per-LED colour + whiteBalance which is blocked by
    # the LAN RCP service-auth gate. Treat "Gen2 confirmed OR unknown" as
    # eligible so cold-start during a cloud outage isn't artificially blocked
    # (Bug 2026-05-20).
    _hw_light = coordinator.hw_version.get(cam_id)
    if (gen2 or _hw_light in (None, "", "CAMERA")) and component in (
        "front",
        "intensity",
    ):
        creds = coordinator.local_creds_cache.get(cam_id)
        cam_host = (
            creds.get("host") if creds else coordinator.rcp_lan_ip_cache.get(cam_id)
        )
        local_user = creds.get("user") if creds else None
        local_pass = creds.get("password") if creds else None
        if cam_host:
            from bosch_shc_camera_client.rcp import rcp_local_write_front_light

            if component == "front":
                # Boolean toggle: 0 = off, 100 = on (full brightness on restore)
                brightness = 100 if value else 0
            else:
                # intensity: int 0-100 or float 0.0-1.0
                brightness = (
                    int(value * 100)
                    if isinstance(value, float) and value <= 1.0
                    else int(value)
                )
            local_session = async_get_clientsession(coordinator.hass, verify_ssl=False)
            local_ok = await rcp_local_write_front_light(
                local_session,
                cam_host,
                brightness,
                user=local_user,
                password=local_pass,
            )
            if local_ok:
                _LOGGER.info(
                    "cloud_set_light_component: cloud failed, Gen2 LOCAL RCP succeeded for %s %s=%s",
                    cam_id[:8],
                    component,
                    value,
                )
                _now = time.monotonic()
                cache_entry = coordinator.shc_state_cache.setdefault(cam_id, {})
                if component == "front":
                    cache_entry["front_light"] = value
                else:
                    cache_entry["front_light_intensity"] = value
                cache_entry["camera_light"] = cache_entry.get(
                    "front_light"
                ) or cache_entry.get("wallwasher")
                coordinator.light_set_at[cam_id] = _now
                if hasattr(coordinator, "local_write_at"):
                    coordinator.local_write_at[cam_id] = _now
                coordinator.async_update_listeners()
                return True
            _LOGGER.debug(
                "cloud_set_light_component: Gen2 LOCAL RCP fallback failed for %s %s — "
                "camera may not accept unauthenticated writes",
                cam_id[:8],
                component,
            )
    _component_labels = {
        "front": "Frontlicht",
        "wallwasher": "Wallwasher",
        "intensity": "Licht-Helligkeit",
    }
    await _notify_write_failed(
        coordinator,
        cam_id,
        f"light_{component}",
        _component_labels.get(component, "Licht"),
        str(value),
    )
    return False


async def async_cloud_set_notifications(
    coordinator: BoschCameraCoordinator, cam_id: str, enabled: bool
) -> bool:
    """Enable (FOLLOW_CAMERA_SCHEDULE) or disable (ALWAYS_OFF) notifications via cloud API.

    Uses PUT /v11/video_inputs/{id}/enable_notifications.
    """
    token = coordinator.token
    status = "FOLLOW_CAMERA_SCHEDULE" if enabled else "ALWAYS_OFF"
    if not token:
        _LOGGER.warning("cloud_set_notifications: no token for %s", cam_id)
    else:
        session = await async_get_bosch_cloud_session(coordinator.hass)
        url = f"{CLOUD_API}/v11/video_inputs/{cam_id}/enable_notifications"
        body = {"enabledNotificationsStatus": status}

        result = await cloud_put_json(session, token, url, body)
        if result.ok:
            coordinator.shc_state_cache.setdefault(cam_id, {})[
                "notifications_status"
            ] = status
            coordinator.notif_set_at[cam_id] = time.monotonic()
            coordinator.async_update_listeners()
            _LOGGER.debug(
                "cloud_set_notifications: %s -> %s (HTTP %s)",
                cam_id,
                status,
                result.status,
            )
            # No forced refresh — optimistic cache + listeners above suffice; regular tick confirms. Avoids re-registering go2rtc / disrupting unrelated live streams (path C, 2026-05-29).
            return True
        _LOGGER.warning(
            "cloud_set_notifications: HTTP %s for %s", result.status, cam_id
        )

    # No local/SHC fallback exists for this endpoint — cloud is the only path.
    await _notify_write_failed(
        coordinator, cam_id, "notifications", "Benachrichtigungen", status
    )
    return False


async def async_cloud_set_pan(
    coordinator: BoschCameraCoordinator, cam_id: str, position: int
) -> bool:
    """Pan the 360 camera to an absolute position (-120 to +120 degrees).

    Uses PUT /v11/video_inputs/{id}/pan -- no SHC local API needed.
    """
    # Block pan while privacy mode is active (camera shutter closed, motor disabled)
    privacy = coordinator.shc_state_cache.get(cam_id, {}).get("privacy_mode")
    if privacy:
        _LOGGER.debug("cloud_set_pan: blocked — Privacy Mode is ON for %s", cam_id)
        return False

    token = coordinator.token
    if not token:
        _LOGGER.warning("cloud_set_pan: no token for %s", cam_id)
        return False

    session = await async_get_bosch_cloud_session(coordinator.hass)
    url = f"{CLOUD_API}/v11/video_inputs/{cam_id}/pan"

    result = await cloud_put_json(session, token, url, {"absolutePosition": position})
    if result.ok:
        # 200 returns a JSON body with currentAbsolutePosition + ETA;
        # 204 has no body — fall back to the requested position.
        actual = position
        eta = 0
        if result.body is not None:
            actual = result.body.get("currentAbsolutePosition", position)
            eta = result.body.get("estimatedTimeToCompletion", 0)
        coordinator.pan_cache[cam_id] = actual
        coordinator.async_update_listeners()
        _LOGGER.debug(
            "cloud_set_pan: %s -> %d deg (HTTP %s, ETA %dms)",
            cam_id,
            actual,
            result.status,
            eta,
        )
        # No forced refresh — optimistic cache + listeners above suffice; regular tick confirms. Avoids re-registering go2rtc / disrupting unrelated live streams (path C, 2026-05-29).
        return True
    _LOGGER.warning("cloud_set_pan: HTTP %s for %s", result.status, cam_id)
    return False


class SHCCoordinatorMixin:
    """Thin coordinator-facing methods delegating to this module's functions.

    Mixed into BoschCameraCoordinator (see __init__.py's class declaration)
    so `coordinator.shc_configured`/`coordinator.async_cloud_set_pan(...)`
    etc. keep working as properties/methods — every one of them just
    forwards `self` to the corresponding free function above, which is
    where the actual SHC/cloud-setter logic lives. `self: Any` (not a
    concrete `self: BoschCameraCoordinator` annotation) for the same reason
    documented on FrigateCoordinatorMixin (frigate_endpoint.py): mypy
    --strict rejects a concrete self-type here because proving it requires
    knowing BoschCameraCoordinator's bases at this class's own definition
    site, which is circular.
    """

    @property
    def shc_configured(self: Any) -> bool:
        """True if SHC local API is fully configured (IP + certs)."""
        return shc_configured(self)

    @property
    def shc_ready(self: Any) -> bool:
        """True if SHC is configured AND currently considered available."""
        return shc_ready(self)

    def _shc_mark_success(self: Any) -> None:
        _shc_mark_success(self)

    def _shc_mark_failure(self: Any) -> None:
        _shc_mark_failure(self)

    async def _async_shc_request(
        self: Any, method: str, path: str, body: dict[str, Any] | None = None
    ) -> dict[str, Any] | list[Any] | None:
        return await async_shc_request(self, method, path, body)

    async def _async_update_shc_states(self: Any, data: dict[str, Any]) -> None:
        return await async_update_shc_states(self, data)

    async def async_shc_set_camera_light(self: Any, cam_id: str, on: bool) -> bool:
        return await async_shc_set_camera_light(self, cam_id, on)

    async def async_cloud_set_light_component(
        self: Any, cam_id: str, component: str, value: Any
    ) -> bool:
        return await async_cloud_set_light_component(self, cam_id, component, value)

    async def async_shc_set_privacy_mode(self: Any, cam_id: str, enabled: bool) -> bool:
        return await async_shc_set_privacy_mode(self, cam_id, enabled)

    async def async_cloud_set_privacy_mode(
        self: Any, cam_id: str, enabled: bool
    ) -> bool:
        return await async_cloud_set_privacy_mode(self, cam_id, enabled)

    async def async_cloud_set_camera_light(self: Any, cam_id: str, on: bool) -> bool:
        return await async_cloud_set_camera_light(self, cam_id, on)

    async def async_cloud_set_notifications(
        self: Any, cam_id: str, enabled: bool
    ) -> bool:
        return await async_cloud_set_notifications(self, cam_id, enabled)

    async def async_cloud_set_pan(self: Any, cam_id: str, position: int) -> bool:
        return await async_cloud_set_pan(self, cam_id, position)

"""Open a live proxy connection to a camera (LOCAL Digest / REMOTE cloud
proxy), with TLS-proxy setup, go2rtc registration, and pre-warm.

Extracted from __init__.py's BoschCameraCoordinator._try_live_connection_inner
— by far the largest/most complex single method in the coordinator (707
lines), always called under the coordinator's per-camera stream lock
(coordinator.try_live_connection acquires it). Kept as a standalone function
taking `coordinator` explicitly, matching the pattern already used for
poll_statuses/poll_events/run_housekeeping.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

import aiohttp

from .const import CLOUD_API, LAN_RECHECK_FORCE_INTERVAL_SEC, TIMEOUT_PUT_CONNECTION

if TYPE_CHECKING:  # pragma: no cover — only for type hints
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


async def try_live_connection_inner(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    is_renewal: bool = False,
    force_reset: bool = False,
) -> dict[str, Any] | None:
    """Inner implementation of try_live_connection (called under lock)."""
    # Local imports (not top-level): keeps unittest.mock.patch(
    # "custom_components.bosch_shc_camera.X", ...) working the same way it
    # did before this method moved out of __init__.py — those patches
    # target the package's own namespace, not this module's. `_redact_creds`
    # additionally can't be a top-level import at all: __init__.py imports
    # this module, so a top-level `from . import _redact_creds` here would
    # be a real circular import.
    from . import (
        _redact_creds as _redact_creds,
        async_get_bosch_cloud_session as async_get_bosch_cloud_session,
        nvr_recorder as nvr_recorder,
        pre_warm_rtsp as pre_warm_rtsp,
    )

    if force_reset:
        # Recovery rebuild (401 rescue / proxy-died): tear the old session
        # and proxy down HERE, under the per-cam stream lock, so the stop is
        # serialized against any concurrent renewal/heartbeat that is also
        # holding the lock to (re)build the proxy. Doing the stop in the
        # caller (outside the lock) let a renewal publish Stream/go2rtc
        # against the port we'd just killed → frozen image (race 2026-06-01).
        coordinator.live_connections.pop(cam_id, None)
        coordinator.stream_warming.discard(cam_id)
        coordinator.get_session(cam_id).warming_started = float("-inf")
        await coordinator.stop_tls_proxy(cam_id)
    token = coordinator.token
    if not token:
        _LOGGER.warning("try_live_connection: no token available")
        return None

    # Pooled, process-wide Bosch-cloud session (TLS-verified against the
    # Bosch private CA — see cloud_ssl.py). This method spans ~270 lines of
    # stream-setup logic and used to open (and close, in the `finally`
    # below) a fresh TCPConnector+ClientSession on every single call — a
    # fresh TCP+TLS handshake per stream start/renewal/heartbeat. Reusing
    # the shared session gives connection pooling on this hot path; the
    # session itself is closed exactly once, on EVENT_HOMEASSISTANT_STOP
    # (cloud_ssl.async_get_bosch_cloud_session), so the `finally` below must
    # NOT close it anymore (see comment there).
    session = await async_get_bosch_cloud_session(coordinator.hass)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    url = f"{CLOUD_API}/v11/video_inputs/{cam_id}/connection"

    try:
        hq, inst = coordinator.get_quality_params(cam_id)
        # [S7] Direct key read — opts only used for this one key; avoids full dict copy
        conn_type_pref = (
            coordinator.stream_type_override
            or coordinator.entry.options.get("stream_connection_type", "local")
        )
        if conn_type_pref == "local":
            candidates = ["LOCAL"]
        elif conn_type_pref == "auto":
            cfg = coordinator.get_model_config(cam_id)
            # Time-decay the error counter: failures older than the TTL
            # belong to a previous network state (router reboot, transient
            # WLAN dropout). Without decay the cam stays pinned on REMOTE
            # forever because record_stream_success only fires on a
            # successful LOCAL stream — and AUTO has stopped attempting
            # LOCAL by then. Cf. _LOCAL_RESCUE_TTL_SEC / _local_rescue_at.
            # TTL is shorter when LAN is currently reachable (the burst is
            # almost certainly stale) and longer otherwise (LAN may still
            # be flaky — keep the cam on REMOTE a bit longer to avoid
            # ping-pong fallback loops).
            lan_ok = coordinator.lan_tcp_reachable.get(cam_id, (False, 0))[0]
            _STREAM_ERROR_TTL_SEC = 300 if lan_ok else 1800
            err_ts = coordinator.stream_error_at.get(cam_id, 0)
            if err_ts and (time.monotonic() - err_ts) > _STREAM_ERROR_TTL_SEC:
                if coordinator.stream_error_count.get(cam_id, 0) > 0:
                    _LOGGER.info(
                        "AUTO mode: %s stream-error counter aged out "
                        "(%.0fs since last error, LAN=%s) — re-attempting LOCAL",
                        cam_id[:8],
                        time.monotonic() - err_ts,
                        "ok" if lan_ok else "unknown",
                    )
                coordinator.stream_error_count.pop(cam_id, None)
                coordinator.stream_error_at.pop(cam_id, None)
                coordinator.stream_fell_back.pop(cam_id, None)
            # Check if LOCAL should be skipped:
            # 1. Too many consecutive stream errors → fall back to REMOTE
            err_count = coordinator.stream_error_count.get(cam_id, 0)
            if err_count >= cfg.max_stream_errors:
                _LOGGER.warning(
                    "AUTO mode: %s had %d consecutive LOCAL errors — falling back to REMOTE",
                    cam_id[:8],
                    err_count,
                )
                coordinator.stream_fell_back[cam_id] = True
                candidates = ["REMOTE"]
            else:
                # 2. WiFi signal too weak → prefer REMOTE
                wifi = coordinator.wifiinfo_cache.get(cam_id, {}).get(
                    "signalStrength", 100
                )
                if isinstance(wifi, (int, float)) and wifi < cfg.min_wifi_for_local:
                    _LOGGER.info(
                        "AUTO mode: %s WiFi %d%% < %d%% threshold — using REMOTE",
                        cam_id[:8],
                        wifi,
                        cfg.min_wifi_for_local,
                    )
                    candidates = [
                        "REMOTE",
                        "LOCAL",
                    ]  # prefer REMOTE but try LOCAL as fallback
                else:
                    candidates = ["LOCAL", "REMOTE"]
                coordinator.stream_fell_back[cam_id] = False
        else:
            candidates = ["REMOTE"]

        # ── TCP pre-check: skip LOCAL if camera is LAN-unreachable ──────
        # When AUTO mode has both LOCAL and REMOTE as candidates and we
        # know the camera's LAN IP, a 1.5s TCP ping decides immediately —
        # saving 45–100s of pre-warm timeout for cameras on a different
        # network/VLAN or that are powered off. Result is cached 60s so
        # repeated stream starts don't each trigger a fresh ping.
        if "LOCAL" in candidates and "REMOTE" in candidates:
            lan_ip = coordinator.get_cam_lan_ip(cam_id)
            if lan_ip:
                _TCP_TTL = 60.0
                cached_tcp = coordinator.lan_tcp_reachable.get(cam_id)
                now_tcp = time.monotonic()
                if cached_tcp and (now_tcp - cached_tcp[1]) < _TCP_TTL:
                    tcp_ok = cached_tcp[0]
                    _LOGGER.debug(
                        "TCP pre-check cache HIT for %s (%s): %s",
                        cam_id[:8],
                        lan_ip,
                        "reachable" if tcp_ok else "unreachable",
                    )
                else:
                    tcp_ok = await coordinator.async_local_tcp_ping(cam_id)
                    _LOGGER.debug(
                        "TCP pre-check for %s (%s): %s",
                        cam_id[:8],
                        lan_ip,
                        "reachable" if tcp_ok else "unreachable",
                    )
                if not tcp_ok:
                    # issue #47: chicken-and-egg breaker. `lan_ip` may be
                    # stale (camera got a new DHCP lease after a mesh
                    # flap/reboot) — every future pre-check against that
                    # same stale IP would fail forever, and skipping LOCAL
                    # here also skips the ONE call (the LOCAL PUT below)
                    # whose response would tell us the camera's *current*
                    # IP. Rather than trusting an indefinitely-repeatable
                    # "unreachable" verdict, periodically ignore it and let
                    # LOCAL be attempted for real. Cheap: if the camera is
                    # genuinely unreachable, the existing pre-warm-failure
                    # fallback (below) still demotes to REMOTE gracefully —
                    # this only costs one extra connection attempt every
                    # LAN_RECHECK_FORCE_INTERVAL_SEC per camera.
                    now_recheck = time.monotonic()
                    last_forced = coordinator.lan_recheck_forced_at.get(
                        cam_id, float("-inf")
                    )
                    if (now_recheck - last_forced) >= LAN_RECHECK_FORCE_INTERVAL_SEC:
                        coordinator.lan_recheck_forced_at[cam_id] = now_recheck
                        _LOGGER.info(
                            "TCP pre-check: %s unreachable at cached LAN IP %s, "
                            "but forcing a periodic LOCAL retry anyway (last "
                            "forced %s ago) in case the camera's LAN IP changed "
                            "(e.g. a DHCP re-lease) — will fall back to REMOTE "
                            "if this LOCAL attempt genuinely fails",
                            cam_id[:8],
                            lan_ip,
                            "never"
                            if last_forced == float("-inf")
                            else f"{now_recheck - last_forced:.0f}s",
                        )
                        # Deliberately do NOT strip LOCAL from `candidates`
                        # here — let the normal LOCAL-then-REMOTE flow run.
                    else:
                        nvr_wants_local = bool(coordinator.nvr_user_intent.get(cam_id))
                        _LOGGER.info(
                            "TCP pre-check: %s LAN unreachable — skipping LOCAL, "
                            "using REMOTE%s",
                            cam_id[:8],
                            " (Mini-NVR recording will stay stopped/unavailable "
                            "while on REMOTE — LAN-only by design)"
                            if nvr_wants_local
                            else "",
                        )
                        candidates = ["REMOTE"]
                        coordinator.stream_fell_back[cam_id] = True

        # A 401 on PUT /connection means the bearer token was rotated /
        # early-invalidated. _ensure_valid_token() is built for exactly this
        # ("Called ONLY when we get a 401"); refresh once per call and retry
        # the PUT rather than silently failing the whole connection.
        token_refreshed = False
        for type_val in candidates:
            # Reset quality params for each candidate — LOCAL override
            # must not leak into the REMOTE fallback.
            hq, inst = coordinator.get_quality_params(cam_id)
            if type_val == "LOCAL" and coordinator.get_quality(cam_id) == "auto":
                # LOCAL: default to best quality (no bandwidth limit on LAN)
                hq, inst = True, 1
            elif type_val == "REMOTE" and inst == 4:
                # REMOTE proxy doesn't support inst=4 (returns 400).
                # Fall back to inst=2 (balanced, ~7.5 Mbps).
                inst = 2
            try:
                # Timeout covers only the HTTP call — pre-warm runs after.
                async with asyncio.timeout(TIMEOUT_PUT_CONNECTION):
                    resp = await session.put(
                        url,
                        json={"type": type_val, "highQualityVideo": hq},
                        headers=headers,
                    )
                    body = await resp.text()
                    # Recoverable token expiry: refresh once and retry the
                    # same candidate's PUT in-place (covered by this timeout).
                    if resp.status == 401 and not token_refreshed:
                        token_refreshed = True
                        try:
                            token = await coordinator.ensure_valid_token(token)
                        except Exception as err:
                            _LOGGER.warning(
                                "try_live_connection: token refresh after 401 "
                                "failed for %s: %s",
                                cam_id,
                                err,
                            )
                        else:
                            headers["Authorization"] = f"Bearer {token}"
                            _LOGGER.info(
                                "try_live_connection: token expired (401) for "
                                "%s — refreshed, retrying PUT (%s)",
                                cam_id,
                                type_val,
                            )
                            resp = await session.put(
                                url,
                                json={
                                    "type": type_val,
                                    "highQualityVideo": hq,
                                },
                                headers=headers,
                            )
                            body = await resp.text()
                _LOGGER.debug(
                    "PUT /connection type=%s → HTTP %d (%d bytes)",
                    type_val,
                    resp.status,
                    len(body),
                )
                if resp.status in (200, 201):
                    import json as _json

                    result: dict[str, Any] = _json.loads(body)
                    _LOGGER.info(
                        "Live connection opened! type=%s → %s",
                        type_val,
                        _redact_creds(result),
                    )
                    # Always request audio — switch.<cam>_audio is a synced
                    # card-side mute now, not a stream-track toggle (see the
                    # cred-rotation site above). 2026-06-01.
                    audio_param = "&enableaudio=1"
                    # Extract bufferingTime for FFmpeg tuning (LOCAL=500ms, REMOTE=1000ms)
                    buffering_ms = result.get("bufferingTime", 1000)
                    result["_bufferingTime"] = buffering_ms
                    # LOCAL response: {"user": "...", "password": "...", "urls": ["192.168.x.x:443"]}
                    local_user = result.get("user", "")
                    local_pass = result.get("password", "")
                    local_rtsp_url = ""  # guard: set inside `if urls:` below; "" means pre-warm skipped
                    if type_val == "LOCAL" and local_user and local_pass:
                        result["_connection_type"] = "LOCAL"
                        result["_local_user"] = local_user
                        result["_local_password"] = local_pass
                        urls = result.get("urls", [])
                        img_scheme = result.get(
                            "imageUrlScheme", "https://{url}/snap.jpg"
                        )
                        if urls:
                            from urllib.parse import quote as _q

                            cam_addr = urls[0]  # "192.168.x.x:443"
                            # Cache LOCAL creds for cloud-outage fallback paths.
                            # Stays populated after the live connection is torn down.
                            try:
                                _host, _port = cam_addr.split(":")
                                coordinator.local_creds_cache[cam_id] = {
                                    "user": local_user,
                                    "password": local_pass,
                                    "host": _host,
                                    "port": int(_port),
                                    "ts": time.monotonic(),
                                }
                                # issue #47: `_get_cam_lan_ip` prefers
                                # `_rcp_lan_ip_cache` over `_local_creds_cache`
                                # — so if that RCP-sourced cache already held a
                                # (possibly stale, e.g. post-DHCP-re-lease) IP,
                                # it would keep winning forever even after we
                                # just confirmed a working LOCAL connection at
                                # a DIFFERENT, definitely-current address. Sync
                                # it here so both caches agree on the freshest
                                # confirmed-working IP and the TCP pre-check
                                # stops pinging a dead address indefinitely.
                                if coordinator.rcp_lan_ip_cache.get(cam_id) != _host:
                                    _LOGGER.info(
                                        "LAN IP for %s updated via LOCAL "
                                        "connection: %s -> %s",
                                        cam_id[:8],
                                        coordinator.rcp_lan_ip_cache.get(cam_id)
                                        or "(unknown)",
                                        _host,
                                    )
                                    coordinator.rcp_lan_ip_cache[cam_id] = _host
                            except Exception as _e:
                                _LOGGER.debug(
                                    "LOCAL creds cache skip for %s: %s",
                                    cam_id[:8],
                                    _e,
                                )
                            _snap_url = img_scheme.replace("{url}", cam_addr)
                            if "JpegSize=" not in _snap_url:
                                _snap_url += (
                                    "&" if "?" in _snap_url else "?"
                                ) + "JpegSize=1206"
                            result["proxyUrl"] = _snap_url
                            cam_host, cam_port = cam_addr.split(":")
                            proxy_port = await coordinator.start_tls_proxy(
                                cam_id,
                                cam_host,
                                int(cam_port),
                                is_renewal=is_renewal,
                            )
                            eu = _q(local_user, safe="")
                            ep = _q(local_pass, safe="")
                            from .models import get_model_config as _gmc

                            _mcfg = _gmc(coordinator.hw_version.get(cam_id, "CAMERA"))
                            local_rtsp_url = (
                                f"rtsp://{eu}:{ep}@127.0.0.1:{proxy_port}"
                                f"/rtsp_tunnel?inst={inst}{audio_param}&fmtp=1&maxSessionDuration={_mcfg.max_session_duration}"
                            )
                            # Don't set rtspsUrl yet — pre-warm must complete first
                            # so stream_source() returns None until encoder is ready.
                            # rtspsUrl/rtspUrl will be set after pre-warm below.
                    else:
                        # REMOTE response: {"urls": ["proxy-NN:42090/{hash}"]}
                        urls = result.get("urls", [])
                        cloud_rtsps_url = None
                        if urls:
                            proxy_host_path = urls[0]
                            result["proxyUrl"] = (
                                f"https://{proxy_host_path}/snap.jpg?JpegSize=1206"
                            )
                            rtsps_host_path = proxy_host_path.replace(":42090", ":443")
                            cloud_rtsps_url = (
                                f"rtsps://{rtsps_host_path}/rtsp_tunnel"
                                f"?inst={inst}{audio_param}&fmtp=1&maxSessionDuration=3600"
                            )
                        elif result.get("hash"):
                            h = result["hash"]
                            ph = result.get(
                                "proxyHost", "proxy-01.live.cbs.boschsecurity.com"
                            )
                            pp = result.get("proxyPort", 42090)
                            result["proxyUrl"] = (
                                f"https://{ph}:{pp}/{h}/snap.jpg?JpegSize=1206"
                            )
                            cloud_rtsps_url = (
                                f"rtsps://{ph}:443/{h}/rtsp_tunnel"
                                f"?inst={inst}{audio_param}&fmtp=1&maxSessionDuration=3600"
                            )
                        if cloud_rtsps_url:
                            # Run a Python TLS proxy for REMOTE too, symmetric to LOCAL.
                            # Bosch Cloud serves session URLs on hosts like
                            # proxy-NN.live.cbs.boschsecurity.com but the cert SAN list
                            # only covers *.residential.connect.boschsecurity.com —
                            # go2rtc's Go RTSP client refuses with `tls: failed to
                            # verify certificate`. The proxy terminates TLS in Python
                            # (verify_mode=CERT_NONE, check_hostname=False) and re-
                            # exports as plain RTSP on 127.0.0.1:N — both FFmpeg (HLS
                            # path) and go2rtc (WebRTC path) consume without scheme
                            # tricks. Falls back to direct rtsps:// if proxy startup
                            # fails (HLS still works that way; WebRTC still cert-
                            # blocked, identical to v10.3.24 behavior).
                            try:
                                from urllib.parse import urlparse as _up

                                parsed = _up(cloud_rtsps_url)
                                pq = parsed.path + (
                                    f"?{parsed.query}" if parsed.query else ""
                                )
                                proxy_port = await coordinator.start_tls_proxy(
                                    cam_id,
                                    parsed.hostname or "",
                                    parsed.port or 443,
                                )
                                local_rtsp_url = f"rtsp://127.0.0.1:{proxy_port}{pq}"
                                result["rtspsUrl"] = local_rtsp_url
                                result["rtspUrl"] = local_rtsp_url
                                result["_remote_origin_url"] = cloud_rtsps_url
                                # `_connection_type`/`_remote_path` power both
                                # `remote_resolve_inner` (the credential-free-
                                # in-spirit REMOTE front-door below) and 3
                                # PRE-EXISTING call sites that already checked
                                # for `_connection_type == "REMOTE"` but were
                                # silently dead code because this field was
                                # never actually set for REMOTE before now:
                                # `session_renewal.remote_session_terminator`
                                # (clean pre-cap session teardown),
                                # `session_renewal.promote_to_local` (live
                                # REMOTE->LOCAL promotion when LAN becomes
                                # reachable again), and `_rcp_read_active`'s
                                # REMOTE branch (opportunistic RCP+ reads via
                                # the cloud-proxy hash). `_remote_path` is
                                # `pq` — the same hash-bearing path+query
                                # already used to build `local_rtsp_url`
                                # above, kept as its own field (rather than
                                # re-parsed from `_remote_origin_url`) so
                                # `remote_resolve_inner` doesn't need to
                                # re-run urlparse on every client connect.
                                result["_connection_type"] = "REMOTE"
                                result["_remote_path"] = pq
                                _LOGGER.debug(
                                    "REMOTE TLS proxy %s: %s → %s",
                                    cam_id[:8],
                                    parsed.hostname,
                                    local_rtsp_url[:80],
                                )
                            except Exception as err:
                                _LOGGER.warning(
                                    "REMOTE TLS proxy start failed for %s — falling back "
                                    "to direct rtsps:// (HLS works, WebRTC will cert-fail): %s",
                                    cam_id[:8],
                                    err,
                                )
                                result["rtspsUrl"] = cloud_rtsps_url
                                result["rtspUrl"] = cloud_rtsps_url
                            else:
                                # TLS proxy succeeded — result["rtspsUrl"] is
                                # already the working, TLS-proxied
                                # local_rtsp_url. Now try to upgrade it to
                                # the stable-URL, hash-free REMOTE front-door
                                # (remote_viewing_front_door.py) — same
                                # go2rtc native-registration-leak rationale
                                # as the LOCAL front-door below, just for the
                                # lower-frequency (session-boundary, roughly
                                # hourly) REMOTE URL churn.
                                #
                                # Deliberately its OWN narrow try/except, NOT
                                # folded into the block above: that block's
                                # `except Exception` falls back to the RAW,
                                # un-proxied `cloud_rtsps_url` — appropriate
                                # when the TLS proxy itself never came up,
                                # but wrong here, where the proxy already
                                # works. `start_remote_viewing_front_door`
                                # already turns its own expected failure mode
                                # (OSError — no free port) into a clean
                                # `None` return; this guard is only for a
                                # genuinely unexpected exception, and it must
                                # not discard the already-working proxied
                                # stream for a bug in an unrelated, optional
                                # feature (bug-hunt finding 2026-07-14: an
                                # earlier version of this code shared the
                                # block above's except and could silently
                                # downgrade a healthy REMOTE session to the
                                # cert-failing raw URL on any front-door bug).
                                try:
                                    remote_front_door_url = await coordinator.start_remote_viewing_front_door(
                                        cam_id,
                                        inst=inst,
                                        audio_param=audio_param,
                                        # REMOTE's cloud_rtsps_url hardcodes
                                        # maxSessionDuration=3600 above (not
                                        # the per-model _mcfg value LOCAL
                                        # uses) — match it so the published
                                        # URL's query string stays consistent
                                        # with what REMOTE has always sent.
                                        max_session_duration=3600,
                                    )
                                except Exception as fd_err:
                                    _LOGGER.warning(
                                        "REMOTE viewing front-door start failed for %s "
                                        "— falling back to the raw TLS-proxied URL "
                                        "(front-door benefit lost, streaming still "
                                        "works): %s",
                                        cam_id[:8],
                                        fd_err,
                                    )
                                    remote_front_door_url = None
                                if remote_front_door_url is not None:
                                    result["rtspsUrl"] = remote_front_door_url
                                    result["rtspUrl"] = remote_front_door_url
                                # else: front-door bind failed — fall back to
                                # the already-set hash-bearing local_rtsp_url
                                # (still TLS-proxied, still works) so
                                # streaming isn't blocked by this feature.
                    coordinator.live_connections[cam_id] = result
                    coordinator.live_opened_at[cam_id] = time.monotonic()

                    # ── LOCAL encoder warm-up (model-specific) ────────
                    # Camera needs time after PUT /connection before the
                    # RTSP encoder produces valid H.264 frames. Timing
                    # varies by model: CAMERA_360 (indoor) ~5s, CAMERA_EYES
                    # (outdoor) ~25s. Pre-warm sends DESCRIBE until the
                    # camera responds, plus a safety buffer. The RTSP URL
                    # is withheld from stream_source() until ready.
                    if type_val == "LOCAL" and local_user and local_pass:
                        coordinator.stream_warming.add(cam_id)
                        coordinator.get_session(
                            cam_id
                        ).warming_started = time.monotonic()
                        # Stop HA's existing Stream now — the PUT above
                        # just rotated creds and the TLS proxy just
                        # switched ports, so FFmpeg's cached URL is dead.
                        # Without stopping here, FFmpeg keeps retrying
                        # the stale URL during the pre-warm wait (up to
                        # min_total_wait seconds), racks up
                        # max_stream_errors, and trips the worker-error
                        # listener into a REMOTE fallback before we ever
                        # call update_source() with the new URL.
                        #
                        # Applies to BOTH renewals AND fresh user-toggles.
                        # On a fresh toggle, a stale Stream object can
                        # still be present if a previous session was torn
                        # down at the URL level but HA's internal Stream
                        # cache held on to the worker. Reusing that worker
                        # via update_source() risks serving a *different
                        # camera's* cached buffer to this entity (observed
                        # 2026-04-27: two camera cards on one dashboard
                        # showed the same video for whichever camera was
                        # toggled last — Stream-Object Reuse-Race). Always
                        # forcing a fresh Stream eliminates that class of
                        # bugs at the cost of one extra FFmpeg cold-start
                        # per stream-on (negligible — the pre-warm already
                        # dominates the activation time).
                        cam_ent = coordinator.camera_entities.get(cam_id)
                        if cam_ent is not None:
                            stale = getattr(cam_ent, "stream", None)
                            if stale is not None:
                                # Hard 5 s timeout: if HA's stream_worker
                                # is stuck in a reconnect-loop against an
                                # expired URL (e.g. a prior REMOTE session
                                # whose relay-side cap already passed),
                                # `stale.stop()` awaits the worker to exit
                                # and never returns — pinning this whole
                                # coroutine and the per-cam stream lock,
                                # which makes every subsequent switch-ON
                                # fail with "already in progress" until
                                # the integration is reloaded. Force-
                                # detach instead; HA will GC the worker.
                                try:
                                    await asyncio.wait_for(stale.stop(), timeout=5)
                                except TimeoutError:
                                    # HA's `Stream.stop()` already set its
                                    # internal `_thread_quit` Event before
                                    # awaiting the worker thread's join (see
                                    # homeassistant.components.stream.Stream._stop)
                                    # — so by the time OUR 5s wait_for gives
                                    # up, the quit signal is already in
                                    # flight. `Stream` runs the worker as a
                                    # raw `threading.Thread` (name
                                    # "stream_worker") with no public cancel
                                    # API beyond that Event; Python offers
                                    # no safe way to force-kill a thread
                                    # blocked in a foreign-code (PyAV/FFmpeg
                                    # read) call. Reaching into `Stream`'s
                                    # private `_thread`/`_thread_quit`
                                    # attributes here to attempt a harder
                                    # cancel would be exactly the kind of
                                    # HA-internals coupling this module
                                    # otherwise avoids, for a thread that
                                    # (per the quit Event already being set)
                                    # should exit on its own once the
                                    # blocking call unblocks. Known
                                    # limitation, not silently swallowed:
                                    # best-effort detach + a WARNING with a
                                    # per-cam repeat counter so a camera
                                    # that keeps tripping this (accumulating
                                    # zombie workers) is visible in the logs.
                                    zombie_count = (
                                        coordinator.zombie_stream_worker_count.get(
                                            cam_id, 0
                                        )
                                        + 1
                                    )
                                    coordinator.zombie_stream_worker_count[cam_id] = (
                                        zombie_count
                                    )
                                    _LOGGER.warning(
                                        "%s: stale Stream.stop() for %s timed out after "
                                        "5s — force-detaching. Its stream_worker thread "
                                        "may still be running (HA exposes no cancel API "
                                        "for a stuck worker); this camera has now hit "
                                        "this timeout %d time(s) since startup",
                                        "Renewal" if is_renewal else "Fresh toggle",
                                        cam_id[:8],
                                        zombie_count,
                                    )
                                except Exception as _exc:
                                    _LOGGER.debug(
                                        "%s: stale Stream.stop() for %s failed: %s",
                                        "Renewal" if is_renewal else "Fresh toggle",
                                        cam_id[:8],
                                        _exc,
                                    )
                                cam_ent.stream = None
                                _LOGGER.debug(
                                    "%s: invalidated stale Stream for %s before pre-warm",
                                    "Renewal" if is_renewal else "Fresh toggle",
                                    cam_id[:8],
                                )
                        cfg = coordinator.get_model_config(cam_id)
                        hw = coordinator.hw_version.get(cam_id, "?")
                        put_time = time.monotonic()
                        proxy_port_val = coordinator.tls_proxy_ports.get(cam_id)
                        if proxy_port_val:
                            _LOGGER.debug(
                                "LOCAL pre-warm for %s (%s, hw=%s): delay=%ds, retries=%d, wait=%ds, buffer=%ds, min_total=%ds",
                                cam_id[:8],
                                cfg.display_name,
                                hw,
                                cfg.pre_warm_delay,
                                cfg.pre_warm_retries,
                                cfg.pre_warm_retry_wait,
                                cfg.post_warm_buffer,
                                cfg.min_total_wait,
                            )
                            await asyncio.sleep(cfg.pre_warm_delay)
                            prewarm_ok = await pre_warm_rtsp(
                                proxy_port_val,
                                local_user,
                                local_pass,
                                cam_addr.split(":")[0],
                                max_attempts=cfg.pre_warm_retries,
                                retry_wait=cfg.pre_warm_retry_wait,
                                post_success_wait=cfg.post_warm_buffer,
                                describe_timeout=cfg.describe_timeout,
                                max_session_duration=cfg.max_session_duration,
                            )
                        else:
                            prewarm_ok = False
                        # If pre-warm failed AND auto mode has REMOTE as a
                        # later candidate, abandon this LOCAL attempt and
                        # fall through to the next candidate. Without this
                        # the integration would pin the user on a dead
                        # LOCAL URL (camera LAN unreachable, firewalled
                        # subnet, different VLAN, etc.) and HA's stream
                        # worker would cycle yellow→blue→yellow forever.
                        # In "local" mode there's nothing to fall back to,
                        # so keep the LOCAL URL so the user can see the
                        # actual failure mode.
                        if (
                            not prewarm_ok
                            and "REMOTE" in candidates
                            and type_val == "LOCAL"
                        ):
                            _LOGGER.warning(
                                "LOCAL pre-warm failed for %s — camera LAN unreachable? "
                                "Falling back to REMOTE.",
                                cam_id[:8],
                            )
                            coordinator.stream_warming.discard(cam_id)
                            coordinator.get_session(cam_id).warming_started = float(
                                "-inf"
                            )
                            coordinator.live_connections.pop(cam_id, None)
                            await coordinator.stop_tls_proxy(cam_id)
                            coordinator.stream_fell_back[cam_id] = True
                            continue  # try next candidate (REMOTE)
                        if not prewarm_ok:
                            # LOCAL-only mode: no REMOTE candidate to fall back to.
                            # Pre-warm failed (camera rejected TLS handshakes or
                            # RTSP DESCRIBE), so the URL we are about to expose
                            # won't actually stream. Clear the warm-up flag now
                            # rather than holding it through the min_total_wait
                            # sleep — otherwise the user gets locked out of the
                            # privacy toggle for ~25s on Indoor / ~100s on
                            # Outdoor while the encoder warm-up they paid for
                            # has already definitively failed. Regression
                            # 2026-05-19 (Innenbereich): TLS proxy reset 3×,
                            # warm-up held the privacy switch hostage.
                            _LOGGER.warning(
                                "LOCAL pre-warm failed for %s without REMOTE fallback — "
                                "clearing warm-up flag so privacy toggle stays responsive",
                                cam_id[:8],
                            )
                            coordinator.stream_warming.discard(cam_id)
                            coordinator.get_session(cam_id).warming_started = float(
                                "-inf"
                            )
                        # Ensure minimum total time from PUT /connection.
                        # Renewals use 2/3 of this (camera encoder already warm).
                        min_wait = (
                            (cfg.min_total_wait * 2 // 3)
                            if is_renewal
                            else cfg.min_total_wait
                        )
                        elapsed = time.monotonic() - put_time
                        remaining = min_wait - elapsed
                        if remaining > 0:
                            _LOGGER.debug(
                                "LOCAL %s: waiting %.0fs more (%.0fs elapsed, min %ds)",
                                cam_id[:8],
                                remaining,
                                elapsed,
                                cfg.min_total_wait,
                            )
                            await asyncio.sleep(remaining)
                        # Set URL — encoder should be ready now. Prefer the
                        # credential-free, stable-port viewing front-door
                        # (viewing_front_door.py) over the raw credentialed
                        # local_rtsp_url: HA-core's own go2rtc integration
                        # auto-registers whatever stream_source() returns on
                        # every WebRTC offer, and can never remove a stale
                        # entry (dedup is by exact URL string) — a rotating-
                        # cred, rotating-port URL would leak a new go2rtc
                        # entry on every credential rotation (as fast as
                        # ~15s on Gen1 cameras). The front-door reuses this
                        # same inner TLS proxy port + live session and
                        # injects the Digest auth itself, so the published
                        # URL never changes across cred rotations.
                        front_door_url = await coordinator.start_viewing_front_door(
                            cam_id,
                            inst=inst,
                            audio_param=audio_param,
                            max_session_duration=_mcfg.max_session_duration,
                        )
                        if front_door_url is not None:
                            result["rtspsUrl"] = front_door_url
                            result["rtspUrl"] = front_door_url
                        else:
                            # Front-door bind failed (extremely rare — e.g.
                            # no free ports at all) — fall back to the
                            # credentialed URL so streaming still works,
                            # just without the credential-free/stable-port
                            # benefit this session.
                            result["rtspsUrl"] = local_rtsp_url
                            result["rtspUrl"] = local_rtsp_url
                        coordinator.live_connections[cam_id] = result  # update with URL
                        coordinator.stream_warming.discard(cam_id)

                    rtsps_url = result.get("rtspsUrl", "")

                    # ── Update HA's stream with new URL ──────────────
                    # AFTER pre-warm so FFmpeg connects to a ready encoder.
                    cam_entity = coordinator.camera_entities.get(cam_id)
                    if cam_entity is not None and rtsps_url:
                        if (
                            hasattr(cam_entity, "stream")
                            and cam_entity.stream is not None
                        ):
                            try:
                                cam_entity.stream.update_source(rtsps_url)
                                # Never log the RTSPS URL or anything derived
                                # from it — it embeds Digest credentials
                                # (user:password@) and the proxy session-hash
                                # token. The cam id alone identifies the event.
                                _LOGGER.debug(
                                    "Stream.update_source() applied for %s",
                                    cam_id[:8],
                                )
                            except Exception as err:
                                _LOGGER.debug(
                                    "Stream.update_source() failed for %s — forcing stream rebuild: %s",
                                    cam_id[:8],
                                    err,
                                )
                                cam_entity.stream = None
                        else:
                            cam_entity.stream = None

                    # ── Push WebRTC provider discovery (AFTER pre-warm) ──
                    # go2rtc registration itself is no longer done manually
                    # here — HA-core's own bundled go2rtc WebRTCProvider
                    # auto-registers whatever stream_source() returns on
                    # every WebRTC offer / snapshot request (confirmed by
                    # reading homeassistant/components/go2rtc/__init__.py's
                    # _update_stream_source), and since both LOCAL
                    # (viewing_front_door.py) and REMOTE
                    # (remote_viewing_front_door.py) now publish a stable,
                    # never-changing URL per session, native lazy
                    # registration no longer risks leaking a fresh go2rtc
                    # entry on every credential rotation the way it would
                    # have with the old raw credentialed/hash-bearing URLs
                    # (HA-Core-submission-prep, 2026-07-14). The explicit
                    # provider-refresh push below is still needed on its own
                    # merits, independent of registration: without it, HA's
                    # auto-refresh runs async ~100 ms-4 s later and the
                    # card's `camera/webrtc/offer` races against it — the
                    # card sends the offer before the provider was wired, HA's
                    # `require_webrtc_support` decorator rejects with
                    # `Camera does not support WebRTC,
                    # frontend_stream_types={HLS}`, card falls to HLS
                    # for the whole session. Explicit refresh here
                    # eliminates the race.
                    if rtsps_url:
                        cam_ent = coordinator.camera_entities.get(cam_id)
                        if cam_ent is not None:
                            try:
                                await cam_ent.async_refresh_providers()
                            except Exception as err:
                                _LOGGER.debug(
                                    "post-connect refresh_providers failed for %s: %s",
                                    cam_id[:8],
                                    err,
                                )

                    # ── LOCAL session auto-renewal ───────────────────
                    if type_val == "LOCAL" and local_user and local_pass:
                        gen = coordinator.get_session(cam_id).generation + 1
                        coordinator.get_session(cam_id).generation = gen
                        coordinator.replace_renewal_task(
                            cam_id, coordinator.auto_renew_local_session(cam_id, gen)
                        )
                        # Green IT idle reaper: tears the session down once
                        # nobody consumes it (tab closed / navigated away /
                        # Cast stopped), regardless of switch state. An active
                        # viewer or recorder counts as a consumer.
                        # OPT-IN / default OFF (under development): WebRTC
                        # viewers don't reliably surface as go2rtc consumers,
                        # so the reaper can false-negative and kill a watched
                        # stream — parked until detection is reworked. Match
                        # the const.py DEFAULT_OPTIONS default (False).
                        if coordinator.entry.options.get("enable_green_it", False):
                            coordinator.replace_reaper_task(
                                cam_id, coordinator.idle_session_reaper(cam_id, gen)
                            )
                    # ── REMOTE session lifetime watchdog ─────────────
                    # The relay drops the RTSP TCP at the URL's
                    # maxSessionDuration boundary with a hard reset, which
                    # leaves HA's stream_worker in a tight reconnect loop
                    # against a dead URL until HLS times out. We schedule a
                    # clean teardown ~60s before that boundary so the switch
                    # flips OFF gracefully and the user sees a defined
                    # state instead of a buffering spinner.
                    elif type_val == "REMOTE":
                        gen = coordinator.get_session(cam_id).generation + 1
                        coordinator.get_session(cam_id).generation = gen
                        coordinator.replace_renewal_task(
                            cam_id, coordinator.remote_session_terminator(cam_id, gen)
                        )
                    # Full coordinator refresh re-evaluates ALL cameras. On a
                    # transparent session RENEWAL nothing user-visible
                    # changes — the stream stays up, unaffected by the
                    # rotated creds since the published front-door URL is
                    # stable — so skip the cross-camera refresh on renewal
                    # (the regular ≤60s tick confirms state). A fresh toggle
                    # still refreshes so provider/state propagate now.
                    if not is_renewal:
                        coordinator.hass.async_create_task(
                            coordinator.async_request_refresh()
                        )
                    coordinator.hass.async_create_task(
                        coordinator.check_and_recover_webrtc(cam_id)
                    )
                    # Opportunistic RCP+ state pull: refresh privacy + LED-dimmer
                    # via lokales / Cloud-Proxy RCP+ on the freshly opened session.
                    # No-op silently on failure; fallback paths (SHC + cloud
                    # /v11/video_inputs) keep their primacy.
                    coordinator.hass.async_create_task(
                        coordinator.refresh_rcp_state(cam_id)
                    )
                    # ── NVR sidecar reaction ─────────────────────────
                    # The recorder follows the live-session connection
                    # type. On a fresh LOCAL session, start (or re-start
                    # with new creds) ffmpeg if user-intent is set. On a
                    # REMOTE session, stop any running recorder cleanly —
                    # LAN-only is a hard line per concept §2.
                    if coordinator.nvr_user_intent.get(cam_id):
                        if type_val == "LOCAL":
                            coordinator.hass.async_create_task(
                                nvr_recorder.start_recorder(coordinator, cam_id),
                                name=f"bosch_nvr_start_{cam_id[:8]}",
                            )
                        elif (
                            type_val == "REMOTE" and cam_id in coordinator.nvr_processes
                        ):
                            coordinator.hass.async_create_task(
                                nvr_recorder.stop_recorder(coordinator, cam_id),
                                name=f"bosch_nvr_stop_{cam_id[:8]}",
                            )
                    return result
                if resp.status == 401:
                    # Still 401 after the in-place token refresh for THIS
                    # candidate. Don't abort the whole call — in AUTO mode
                    # (candidates=[LOCAL, REMOTE]) a LOCAL 401 (camera
                    # unreachable / wrong network) must still let REMOTE be
                    # tried. Fall through to the next candidate; the loop's
                    # post-amble returns None only when ALL types failed.
                    _LOGGER.warning(
                        "try_live_connection: still 401 for %s (type=%s) "
                        "after token refresh — skipping this candidate",
                        cam_id,
                        type_val,
                    )
                else:
                    _LOGGER.warning(
                        "try_live_connection: HTTP %d for type=%s: %s",
                        resp.status,
                        type_val,
                        body[:200],
                    )
            except TimeoutError:
                _LOGGER.warning("try_live_connection: timeout for type=%s", type_val)
            except aiohttp.ClientError as err:
                _LOGGER.warning(
                    "try_live_connection: connection error for type=%s: %s",
                    type_val,
                    err,
                )
    finally:
        # Do NOT close `session` here — it is the pooled, process-wide Bosch
        # cloud session (cloud_ssl.async_get_bosch_cloud_session), shared
        # across every coordinator tick/renewal/heartbeat and every other
        # module that talks to the Bosch cloud. It is closed exactly once,
        # on EVENT_HOMEASSISTANT_STOP, by cloud_ssl.py itself. Closing it
        # here (as the previous per-call ClientSession was) would tear down
        # every other in-flight Bosch cloud call sharing this session.
        pass

    _LOGGER.warning("Could not open live connection for %s — all types failed", cam_id)
    return None

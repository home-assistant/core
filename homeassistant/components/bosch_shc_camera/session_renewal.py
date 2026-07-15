"""LOCAL/REMOTE live-session keepalive, cred refresh, and lifetime capping.

Phase 3 step 2 of the coordinator-rewrite split (see
docs/stream-perf-stability-refactor-plan.md). Pure structural move: the
bodies below are the former `BoschCameraCoordinator` methods
`_refresh_local_creds_from_heartbeat`, `_auto_renew_local_session`,
`_promote_to_local` and `_remote_session_terminator`, unchanged except for
`self` → `coordinator`. `BoschCameraCoordinator` keeps a thin same-named
method for each that delegates here — these functions are exercised
extensively from other coordinator-facing modules (live_connection.py,
camera_status.py) and from the test suite both as bound methods and via
`BoschCameraCoordinator._method(coord, ...)` unbound-style calls plus direct
`AsyncMock()` attribute patching — all of which requires the method to keep
existing on the class. Keeping the thin dispatch avoids rewriting that
entire call surface for a purely structural move.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from .cloud_ssl import async_bosch_cloud_session_cm
from .const import CLOUD_API, TIMEOUT_PUT_CONNECTION

if TYPE_CHECKING:  # pragma: no cover — only for type hints
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


async def refresh_local_creds_from_heartbeat(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    resp_text: str,
    generation: int,
    elapsed: float,
) -> None:
    """Cache fresh LOCAL creds from a heartbeat PUT response and rebuild the cached rtspsUrl.

    This ensures the next stream-worker restart picks them up.

    Bosch's PUT /v11/video_inputs/{id}/connection LOCAL returns a fresh
    digest user/password pair on every call; the previous pair stops
    accepting NEW RTSP connects within ~60 s (the maxSessionDuration
    default Bosch announces). The active RTSP connection survives, but
    without this refresh a reconnect after idle would fail with HTTP 401
    and trip the LOCAL→REMOTE fallback. Capture analysis in
    captures/api-findings.md §1 shows the iOS app handles this by
    firing PUT at ~5 Hz during live view; we settle for one PUT per
    heartbeat_interval (30 s on Indoor) which is more than enough.

    The handler is best-effort: any parse / state error is swallowed,
    the heartbeat keeps running, and the reactive 401 rescue in
    _handle_stream_worker_error remains as a safety net.

    Async (issue #42 follow-up) so the live-dict mutation can serialize
    against `recorder.start_recorder`'s spawn tail via
    `_get_nvr_recorder_lock` instead of only shrinking the race window.
    """
    try:
        import json as _json
        from urllib.parse import quote as _q

        rj = _json.loads(resp_text or "{}")
        new_user = rj.get("user")
        new_pass = rj.get("password")
        if not (new_user and new_pass):
            return  # response without creds — nothing to refresh
        live = coordinator.live_connections.get(cam_id)
        if not live or live.get("_connection_type") != "LOCAL":
            return  # session torn down or already on REMOTE
        old_user = live.get("_local_user")
        old_pass = live.get("_local_password")
        if old_user == new_user and old_pass == new_pass:
            return  # creds unchanged (rare but possible — skip noisy update)
        proxy_port = coordinator.tls_proxy_ports.get(cam_id)
        if not proxy_port:
            return  # TLS proxy not running — nothing to point the URL at
        old_url = live.get("rtspsUrl") or live.get("rtspUrl") or ""
        inst_val = 1
        qs = old_url.split("?", 1)[-1] if "?" in old_url else ""
        for tok in qs.split("&"):
            if tok.startswith("inst="):
                try:
                    inst_val = int(tok.split("=", 1)[1])
                except ValueError:
                    pass
                break
        # Audio track is ALWAYS requested. switch.<cam>_audio is now a
        # lightweight synced MUTE preference applied card-side (video.muted),
        # so toggling it no longer re-opens the stream (AAC ≈ negligible
        # bandwidth) — this is what makes mute/unmute sync instantly across
        # devices and fixes the audio-toggle reconnect jank (#22). 2026-06-01.
        audio_param = "&enableaudio=1"
        mcfg = coordinator.get_model_config(cam_id)
        new_url = (
            f"rtsp://{_q(new_user, safe='')}:{_q(new_pass, safe='')}@"
            f"127.0.0.1:{proxy_port}/rtsp_tunnel?inst={inst_val}"
            f"{audio_param}&fmtp=1&maxSessionDuration={mcfg.max_session_duration}"
        )
        # If the credential-free viewing front-door (viewing_front_door.py)
        # is bound for this camera, stream_source() is already serving its
        # stable, creds-never-in-the-URL address — that URL stays valid
        # across this cred rotation completely unchanged (the front-door
        # reads `_local_user`/`_local_password` fresh on every client
        # connect, updated right below), so it must NOT be overwritten with
        # the raw credentialed `new_url` here. Doing so would silently leak
        # real Digest credentials back into stream_source()'s return value
        # on every heartbeat (as fast as ~15s on Gen1) — exactly the
        # go2rtc-native-registration leak the front-door exists to prevent
        # (go2rtc dedupes purely on exact URL match and can never remove a
        # stale entry, so a rotating URL leaks a fresh entry every
        # rotation). Only the raw-fallback path (front-door bind failed at
        # connect time, see live_connection.py) still needs its published
        # URL rebuilt with the fresh creds here — `old_url` (scraped above,
        # before this rotation touched anything) already IS the currently-
        # published URL either way, so reusing it verbatim when the front-
        # door is active is correct.
        front_door_active = (
            coordinator.viewing_front_door_runner is not None
            and coordinator.viewing_front_door_runner.has_server(cam_id)
        )
        effective_url = old_url if front_door_active else new_url
        # Serialize against recorder.start_recorder's final creds
        # re-read + ffmpeg spawn (issue #42 follow-up) — without this,
        # a heartbeat rotation landing mid-spawn could still hand ffmpeg
        # a cred pair that's stale by the time it connects.
        async with coordinator.get_nvr_recorder_lock(cam_id):
            live["_local_user"] = new_user
            live["_local_password"] = new_pass
            live["rtspsUrl"] = effective_url
            live["rtspUrl"] = effective_url
            cache = coordinator.local_creds_cache.get(cam_id, {})
            cache.update(
                {
                    "user": new_user,
                    "password": new_pass,
                    "ts": time.monotonic(),
                }
            )
            coordinator.local_creds_cache[cam_id] = cache
        cam_entity = coordinator.camera_entities.get(cam_id)
        stream = getattr(cam_entity, "stream", None) if cam_entity else None
        if stream is not None:
            try:
                stream.update_source(effective_url)
            except Exception as err:
                _LOGGER.debug(
                    "Heartbeat: Stream.update_source for %s failed (will heal at next worker restart): %s",
                    cam_id[:8],
                    err,
                )
        # go2rtc (WebRTC) previously needed an explicit re-registration PUT
        # here so WebRTC-only viewers (those never opening an HLS stream)
        # wouldn't 401 once the camera rotated the old creds out — the
        # manual PUT/DELETE registration this served has been removed
        # (HA-Core-submission-prep, 2026-07-14): HA-core's own bundled
        # go2rtc provider auto-registers whatever stream_source() returns on
        # every WebRTC offer, and since the credential-free viewing
        # front-door (viewing_front_door.py) publishes a URL that stays
        # identical across every heartbeat rotation (`effective_url` above
        # is `old_url`, unchanged, whenever the front-door is active), there
        # is no longer a "stale creds baked into an already-registered URL"
        # problem for this to fix — go2rtc's existing registration is
        # already correct and does not need refreshing on a rotation that
        # never changes the published URL.
        # NVR sidecar: unlike a fresh connect, the ESTABLISHED ffmpeg RTSP
        # session survives cred rotation (see docstring above) — no
        # restart needed here. A proactive restart on every heartbeat used
        # to run unconditionally, which on fast-rotating Gen1 cameras
        # (15 s heartbeat) killed and respawned ffmpeg ~4x/minute,
        # truncating every recorded segment to a few seconds (GitHub
        # issue #41). Genuine ffmpeg failures (the connection actually
        # dying, e.g. once creds truly go stale past the ~60 s grace) are
        # already recovered by `_watch_recorder`, which respawns with the
        # freshly-cached `rtspsUrl` set above.
        _LOGGER.debug(
            "Heartbeat refreshed creds for %s (gen=%d, %.0fs into session, user=%s)",
            cam_id[:8],
            generation,
            elapsed,
            new_user,
        )
    except Exception as err:
        _LOGGER.debug(
            "Heartbeat cred-refresh skipped for %s: %s",
            cam_id[:8],
            err,
        )


async def auto_renew_local_session(
    coordinator: BoschCameraCoordinator, cam_id: str, generation: int
) -> None:
    """Keep LOCAL RTSP session alive via heartbeats + periodic full renewal.

    Two mechanisms, both model-specific (from CameraModelConfig):

    1. Cloud heartbeat (every cfg.heartbeat_interval seconds):
       PUT /connection LOCAL — refreshes the cloud-side credential lease.
       Lightweight, does NOT restart TLS proxy or FFmpeg.

    2. Full session renewal (every cfg.renewal_interval seconds):
       Complete session restart — new PUT /connection, new credentials,
       new TLS proxy, Stream.update_source(). Required because some cameras
       (especially outdoor CAMERA_EYES) kill the RTSP TCP connection after
       a few minutes regardless of cloud heartbeats.

    The Bosch app sends PUT /connection every ~1s as heartbeat.
    Indoor cameras are stable for 3500s+, outdoor cameras drop after 2-10 min.
    """
    cfg = coordinator.get_model_config(cam_id)
    heartbeat_interval = cfg.heartbeat_interval
    renewal_interval = cfg.renewal_interval
    _LOGGER.debug(
        "Session keepalive started for %s (gen=%d, heartbeat=%ds, renewal=%ds)",
        cam_id[:8],
        generation,
        heartbeat_interval,
        renewal_interval,
    )
    consecutive_fails = 0
    renewal_fails = 0  # consecutive full-renewal failures (for session_stale)
    session_start = time.monotonic()
    try:
        while True:
            await asyncio.sleep(heartbeat_interval)
            # Stop if a newer generation was started (OFF→ON cycle)
            if coordinator.get_session(cam_id).generation != generation:
                _LOGGER.debug(
                    "Keepalive: stale gen=%d for %s — stopping",
                    generation,
                    cam_id[:8],
                )
                break
            # Stop if stream was turned off
            if cam_id not in coordinator.live_connections:
                _LOGGER.debug("Keepalive: stream off for %s — stopping", cam_id[:8])
                break
            live = coordinator.live_connections.get(cam_id, {})
            if live.get("_connection_type") != "LOCAL":
                _LOGGER.debug("Keepalive: not LOCAL for %s — stopping", cam_id[:8])
                break

            elapsed = time.monotonic() - session_start

            # ── Full session renewal (proactive, time-based) ─────────
            if elapsed >= renewal_interval:
                _LOGGER.info(
                    "Session renewal for %s after %.0fs (interval=%ds)",
                    cam_id[:8],
                    elapsed,
                    renewal_interval,
                )
                try:
                    result = await coordinator.try_live_connection(
                        cam_id, is_renewal=True
                    )
                    if result:
                        _LOGGER.info("Session renewed for %s", cam_id[:8])
                        renewal_fails = 0
                        if coordinator.session_stale.get(cam_id):
                            coordinator.session_stale[cam_id] = False
                            _LOGGER.info(
                                "Session recovered for %s — stale flag cleared",
                                cam_id[:8],
                            )
                    else:
                        renewal_fails += 1
                        _LOGGER.warning(
                            "Session renewal failed for %s — retrying next cycle",
                            cam_id[:8],
                        )
                        session_start = time.monotonic()  # reset to avoid spamming
                except Exception as exc:
                    renewal_fails += 1
                    _LOGGER.warning("Session renewal error for %s: %s", cam_id[:8], exc)
                    session_start = time.monotonic()
                # Mark session stale after 3 consecutive renewal failures so
                # entities can surface "unavailable" instead of silently
                # showing a frozen picture.
                if renewal_fails >= 3 and not coordinator.session_stale.get(cam_id):
                    coordinator.session_stale[cam_id] = True
                    _LOGGER.warning(
                        "Session renewal persistently failing for %s (%d consecutive)",
                        cam_id[:8],
                        renewal_fails,
                    )
                # try_live_connection creates a NEW heartbeat task with new generation,
                # so this loop will exit at the stale-gen check above.
                continue

            # ── Lightweight cloud heartbeat ───────────────────────────
            # Bosch rotates the per-session digest creds on EVERY successful
            # PUT /connection LOCAL (verified across all captures, see
            # captures/api-findings.md §1). The original creds remain valid
            # for the active RTSP connection as long as FFmpeg keeps the
            # session alive — but a reconnect after RTSP idle (HLS consumer
            # disconnect) gets HTTP 401 because the ~14-min-old creds were
            # rotated out long ago by 28+ subsequent heartbeats.
            #
            # We parse the response, cache the new creds in the live-session
            # state, rebuild the rtspsUrl with fresh creds, and call
            # Stream.update_source(). HA's stream component changes the
            # source for the next worker restart only — the running worker
            # is not disturbed, so there is no glitch in the live view. When
            # the worker eventually restarts (idle reconnect, crash) it
            # picks up the fresh URL automatically and avoids the 401.
            try:
                token = coordinator.token
                if not token:
                    continue
                # Pooled shared session — a heartbeat fires every ~30 s per
                # camera; a fresh TCP+TLS handshake each time was pure
                # overhead. The CM does NOT close the shared session.
                # 2026-06-18 (perf).
                async with async_bosch_cloud_session_cm(coordinator.hass) as session:
                    url = f"{CLOUD_API}/v11/video_inputs/{cam_id}/connection"
                    async with asyncio.timeout(TIMEOUT_PUT_CONNECTION):
                        async with session.put(
                            url,
                            json={"type": "LOCAL", "highQualityVideo": True},
                            headers={
                                "Authorization": f"Bearer {token}",
                                "Content-Type": "application/json",
                            },
                        ) as resp:
                            resp_text = (
                                await resp.text() if resp.status in (200, 201) else ""
                            )
                            if resp.status in (200, 201):
                                consecutive_fails = 0
                                await coordinator.refresh_local_creds_from_heartbeat(
                                    cam_id,
                                    resp_text,
                                    generation,
                                    elapsed,
                                )
                            else:
                                consecutive_fails += 1
                                _LOGGER.warning(
                                    "Heartbeat HTTP %d for %s (fail %d)",
                                    resp.status,
                                    cam_id[:8],
                                    consecutive_fails,
                                )
            except Exception as exc:
                consecutive_fails += 1
                _LOGGER.warning(
                    "Heartbeat error for %s: %s (fail %d)",
                    cam_id[:8],
                    exc,
                    consecutive_fails,
                )

            # After 3 consecutive heartbeat failures, force immediate renewal
            if consecutive_fails >= 3:
                _LOGGER.warning(
                    "Heartbeat: %d consecutive failures for %s — forcing renewal",
                    consecutive_fails,
                    cam_id[:8],
                )
                consecutive_fails = 0
                try:
                    result = await coordinator.try_live_connection(
                        cam_id, is_renewal=True
                    )
                    if result:
                        _LOGGER.info("Heartbeat: session renewed for %s", cam_id[:8])
                        renewal_fails = (
                            0  # prevent stale flag misfiring after heartbeat rescue
                        )
                    else:
                        _LOGGER.warning("Heartbeat: renewal failed for %s", cam_id[:8])
                        session_start = time.monotonic()
                except Exception as exc:
                    _LOGGER.warning(
                        "Heartbeat: renewal error for %s: %s", cam_id[:8], exc
                    )
                    session_start = time.monotonic()
    except asyncio.CancelledError:
        _LOGGER.debug("Keepalive cancelled for %s (gen=%d)", cam_id[:8], generation)
    finally:
        coordinator.renewal_tasks.pop(cam_id, None)
        _LOGGER.debug("Keepalive loop ended for %s (gen=%d)", cam_id[:8], generation)


async def promote_to_local(coordinator: BoschCameraCoordinator, cam_id: str) -> None:
    """Lift an active REMOTE-fallback stream onto LOCAL via a renewal.

    Triggered from the status loop when the cam's TCP-ping cache flips
    from unreachable → reachable while a stream is currently running on
    REMOTE-fallback. Calls `try_live_connection(is_renewal=True)` which
    — with `_stream_fell_back` already cleared by the caller — runs the
    AUTO candidate list (LOCAL first, REMOTE as fallback) and on a
    successful LOCAL pre-warm invokes `Stream.update_source()` so the
    live HLS session swaps from Cloud to LAN with a brief re-buffer.
    Falls back to REMOTE again on LAN failure (no harm — the stream
    keeps running, just on the original path).
    """
    try:
        live = coordinator.live_connections.get(cam_id, {})
        if not live or live.get("_connection_type") != "REMOTE":
            return
        result = await coordinator.try_live_connection(cam_id, is_renewal=True)
        if not result:
            _LOGGER.debug(
                "Active LOCAL promotion: %s renewal returned None — "
                "stream stays on REMOTE",
                cam_id[:8],
            )
            return
        new_type = result.get("_connection_type")
        if new_type == "LOCAL":
            _LOGGER.info(
                "Active LOCAL promotion: %s migrated REMOTE → LOCAL",
                cam_id[:8],
            )
        else:
            _LOGGER.debug(
                "Active LOCAL promotion: %s renewal landed on %s "
                "(LAN attempt did not stick)",
                cam_id[:8],
                new_type,
            )
    except Exception as err:
        _LOGGER.warning(
            "Active LOCAL promotion failed for %s: %s",
            cam_id[:8],
            err,
        )


async def remote_session_terminator(
    coordinator: BoschCameraCoordinator, cam_id: str, generation: int
) -> None:
    """Schedule a clean teardown of a REMOTE live session before the relay-side lifetime cap.

    Background: when the session reaches `maxSessionDuration` the upstream
    relay drops the RTSP TCP with a hard reset. HA's stream_worker then
    enters a tight reconnect loop against the dead URL until the HLS
    consumer's read timeout fires — anywhere from 30 s (browser) to
    several minutes of buffering spinner depending on the consumer. By
    tearing the stream down ourselves shortly before the cap, the switch
    flips OFF cleanly and the user sees a defined state. A re-toggle
    starts a fresh REMOTE session at full lifetime.

    We do not auto-renew REMOTE: the relay only mints a brand-new URL on
    each PUT /connection, so renewal would force a 30+ s pre-warm window
    every ~58 min — worse UX than a clean stop.

    Generation-tracked the same way as `_auto_renew_local_session`: any
    OFF→ON cycle bumps the session's `generation`, this loop's generation
    check then exits without action.
    """
    cfg = coordinator.get_model_config(cam_id)
    # Tear down 60 s before the URL's maxSessionDuration so the camera
    # never hits the relay-side cap; if the user has shortened the cap
    # via the model config (<=60), still give ourselves 1 s.
    delay = max(1, cfg.max_session_duration - 60)
    _LOGGER.debug(
        "REMOTE session terminator scheduled for %s (gen=%d, %ds until teardown)",
        cam_id[:8],
        generation,
        delay,
    )
    try:
        await asyncio.sleep(delay)
        # Stop if a newer generation was started (OFF→ON cycle, or a
        # subsequent LOCAL upgrade replaced the REMOTE session).
        if coordinator.get_session(cam_id).generation != generation:
            _LOGGER.debug(
                "REMOTE terminator: stale gen=%d for %s — skipping",
                generation,
                cam_id[:8],
            )
            return
        # Stop if the stream was already turned off.
        if cam_id not in coordinator.live_connections:
            _LOGGER.debug(
                "REMOTE terminator: stream already off for %s — skipping",
                cam_id[:8],
            )
            return
        live = coordinator.live_connections.get(cam_id, {})
        if live.get("_connection_type") != "REMOTE":
            _LOGGER.debug(
                "REMOTE terminator: %s is %s now — skipping",
                cam_id[:8],
                live.get("_connection_type"),
            )
            return
        _LOGGER.info(
            "REMOTE session lifetime reached for %s — tearing down cleanly",
            cam_id[:8],
        )
        # Schedule teardown in its OWN task rather than awaiting it here:
        # this terminator is itself registered in `_renewal_tasks[cam_id]`
        # (`_replace_renewal_task`), and `_tear_down_live_stream`'s first
        # action pops+cancels that entry — i.e. it would cancel ITSELF
        # mid-teardown, potentially aborting cleanup after the TLS proxy
        # stops but before go2rtc unregister / `stream.stop()` run. Same
        # trap the idle reaper already avoids (see its comment above).
        coordinator.hass.async_create_task(
            coordinator.tear_down_live_stream(cam_id, expected_generation=generation),
            f"bosch_shc_camera_remote_terminate_{cam_id[:8]}",
        )
        coordinator.hass.async_create_task(coordinator.async_request_refresh())
    except asyncio.CancelledError:
        _LOGGER.debug(
            "REMOTE terminator cancelled for %s (gen=%d)",
            cam_id[:8],
            generation,
        )
    finally:
        coordinator.renewal_tasks.pop(cam_id, None)

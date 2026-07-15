"""Live-stream teardown, worker-error recovery, and idle-session reaping.

Phase 3 step 1 of the coordinator-rewrite split (see
docs/stream-perf-stability-refactor-plan.md). Pure structural move: the
bodies below are the former `BoschCameraCoordinator` methods
`_tear_down_live_stream`, `_schedule_stream_worker_error`,
`_handle_stream_worker_error`, `_go2rtc_consumer_count`,
`_has_active_consumer` and `_idle_session_reaper`, unchanged except for
`self` → `coordinator`. `BoschCameraCoordinator` keeps a thin same-named
method for each that delegates here — these functions are exercised
extensively from other coordinator-facing modules (switch.py, slow_tier.py,
frigate_endpoint.py's `FrigateCoordinatorMixin`, live_connection.py) and
from the shutdown path in `__init__.py` (`async_unload_entry`'s
`getattr(coord, "tear_down_live_stream", None)` duck-typed dispatch, kept
for minimal SimpleNamespace test-fixture compatibility) as bound
`coordinator._method(...)` calls, and from the test suite both as bound
methods and via `BoschCameraCoordinator._method(coord, ...)` unbound-style
calls plus direct `AsyncMock()` attribute patching — all of which requires
the method to keep existing on the class. Keeping the thin dispatch avoids
rewriting that entire call surface for a purely structural move.
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

import aiohttp

from .const import (
    STREAM_HLS_FRESH_SEC,
    STREAM_IDLE_REAP_CHECK_SEC,
    STREAM_IDLE_REAP_SEC,
)
from .go2rtc_client import _go2rtc_client_session

if TYPE_CHECKING:  # pragma: no cover — only for type hints
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


async def tear_down_live_stream(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    expected_generation: int | None = None,
) -> None:
    """Stop an active LOCAL/REMOTE live stream cleanly.

    Shared teardown for:
      * `BoschLiveStreamSwitch.async_turn_off` (user pressed stop).
      * `BoschPrivacyModeSwitch.async_turn_on` (camera shutter closes, any
        streaming session must also end — the TLS proxy's camera-side
        socket is dead anyway once privacy engages).
      * The stream-worker-error listener and health watchdog (when they
        force a REMOTE fallback).

    Steps:
      1. Cancel the LOCAL keepalive task (tracked in `_renewal_tasks`;
         the legacy `_auto_renew_tasks` dict is never populated).
      2. Clear the per-cam session state (`_live_connections`,
         `_live_opened_at`).
      3. Stop the TLS proxy server socket — closing TCP is enough for
         the camera to detect disconnect and drop its RTSP session
         (LED off). Do NOT send PUT /connection here; that starts a
         NEW session and keeps the camera streaming.
      4. Unregister from go2rtc so the shared RTSP→WebRTC endpoint
         stops serving a dead URL.
      5. Stop HA's `Stream` object on the camera entity. Without this
         the stream_worker keeps its cached URL and auto-restarts
         against the (now-dead) TLS proxy forever — that's what
         produced the yellow→blue→yellow cycle reported in #6 when
         Privacy was flipped while a stream was running, and what our
         own `_StreamWorkerErrorListener` would then try to "fix" by
         falling back to REMOTE — which also fails since the camera
         returns HTTP 443 sh:camera.in.privacy.mode.

    Runs entirely under the per-cam stream lock (`_get_stream_lock`) —
    the SAME lock `try_live_connection`/`try_live_connection_inner` hold
    for the whole build/rebuild. Without this, an unlocked call here
    (idle reaper, external-privacy detection, frigate-idle-timeout,
    REMOTE-lifetime terminator — none of them go through
    `try_live_connection`) could race a concurrent renewal: the renewal
    publishes a brand-new proxy port + `Stream.update_source()` first,
    then this teardown runs a beat later and pops `_live_connections`
    (line below) — which also silently defeats `record_stream_error`'s
    LOCAL-only counting — and closes the port the renewal just
    published, leaving the new session dead with no error escalation
    and no automatic recovery (live incident 2026-07-04, Innenbereich:
    stream-worker looped on "Connection refused" against a rotated
    session for 4+ minutes until a manual HA restart).

    `expected_generation`: pass the session's `generation` value the
    caller observed when it DECIDED to tear down (idle reaper,
    frigate-idle-timeout, REMOTE-lifetime terminator — all watchdogs that
    read stale state, then queue this call). Locking closed the old race
    but opened a new one: this call can now block for the whole duration
    of a concurrent rebuild, and a rebuild bumps the generation — so by
    the time it runs, this stale "tear it down" decision may no longer
    apply to whatever session exists NOW (a fresh, healthy, unrelated-to-
    the-original-reason session). Re-checking the generation under the
    lock — before touching any state — lets us bail out instead of
    destroying a session the caller never actually meant to kill. Callers
    with a hard, still-true-regardless-of-session fact (privacy ON, user
    pressed stop) pass `None` (default) — always apply.
    """
    async with coordinator.get_stream_lock(cam_id):
        if (
            expected_generation is not None
            and coordinator.get_session(cam_id).generation != expected_generation
        ):
            _LOGGER.debug(
                "Teardown for %s skipped — session generation changed "
                "(%s) since the caller decided to tear down (expected %s); "
                "a newer rebuild superseded the stale trigger",
                cam_id[:8],
                coordinator.get_session(cam_id).generation,
                expected_generation,
            )
            return
        task = coordinator.renewal_tasks.pop(cam_id, None)
        if task and not task.done():
            task.cancel()
        # Cancel the idle reaper too. When the reaper itself triggers teardown
        # it has already returned (it schedules teardown as a separate task), so
        # this cancel is a no-op in that path; for all other teardown triggers
        # (switch off, privacy on, REMOTE fallback) it stops the reaper loop.
        reaper = coordinator.reaper_tasks.pop(cam_id, None)
        if reaper and not reaper.done():
            reaper.cancel()
        # Step 1 — clear visible state FIRST. BoschLiveStreamSwitch.is_on
        # reads from `_user_intent_streams`; if anything below raises (NVR
        # child gone, file lock, ...) the user-visible switch would otherwise
        # stay stuck on "on". Reported by Thomas 2026-05-19 (Mini-NVR BETA).
        # Reset user intent too — privacy-on, health-watchdog REMOTE-escalation
        # and external teardowns all genuinely end the user's "live stream
        # wanted" intent.
        coordinator.user_intent_streams.discard(cam_id)
        coordinator.live_connections.pop(cam_id, None)
        coordinator.live_opened_at.pop(cam_id, None)
        coordinator.get_session(cam_id).idle_since = None
        # Clear the warm-up flag proactively. is_stream_warming() would lazily
        # clear it (Scenario 1: no live conn), but a privacy-ON teardown is
        # immediately followed by a privacy cooldown check that calls
        # is_stream_warming — leaving it set risks blocking the very next
        # privacy toggle. Discard here so the toggle is never spuriously gated.
        coordinator.stream_warming.discard(cam_id)
        coordinator.get_session(cam_id).warming_started = float("-inf")
        coordinator.stream_error_count.pop(cam_id, None)
        coordinator.stream_error_at.pop(cam_id, None)
        coordinator.stream_fell_back.pop(cam_id, None)
        coordinator.local_rescue_attempts.pop(cam_id, None)
        coordinator.local_rescue_at.pop(cam_id, None)
        # Push the cleared state to HA immediately so the UI flips to "off"
        # without waiting for the next coordinator refresh tick.
        ls_entity = coordinator.live_stream_entities.get(cam_id)
        if ls_entity is not None and getattr(ls_entity, "hass", None) is not None:
            try:
                ls_entity.async_write_ha_state()
            except Exception as exc:  # pragma: no cover — defensive: HA state write
                _LOGGER.debug(
                    "live-stream switch state write for %s skipped: %s",
                    cam_id[:8],
                    exc,
                )
        # Step 2 — stop the NVR sidecar best-effort. Ordering: BEFORE
        # _stop_tls_proxy so ffmpeg gets a chance to flush MP4 cleanly,
        # but AFTER the visible state is corrected. Keep user-intent set
        # so the recorder auto-restarts when the LAN session comes back.
        # Concept §2.
        if cam_id in coordinator.nvr_processes:
            try:
                await coordinator.stop_recorder(cam_id, clear_intent=False)
            except Exception as exc:
                _LOGGER.warning(
                    "stop_recorder for %s raised %s during teardown — "
                    "switch state already cleared, continuing with proxy/stream cleanup",
                    cam_id[:8],
                    exc,
                )
        await coordinator.stop_tls_proxy(cam_id)
        # Viewing front-door (viewing_front_door.py) wraps this same TLS
        # proxy port — stop it right after the proxy so no stray client can
        # be relayed into a proxy that's already gone, and before the
        # go2rtc unregister below (same ordering rationale: tear the
        # publishing layers down inside-out).
        await coordinator.stop_viewing_front_door(cam_id)
        # Same for the REMOTE viewing-path front-door
        # (remote_viewing_front_door.py) — separate runner from the LOCAL
        # one above, but wraps the same per-cam TLS proxy port and must be
        # stopped on every teardown regardless of which connection type
        # this session actually was (a safe no-op if REMOTE's front-door was
        # never bound for this cam_id — same as the LOCAL call above being a
        # no-op for a REMOTE-only session). This is also how
        # `session_renewal.remote_session_terminator`'s pre-cap teardown
        # reaches the front-door: it calls `_tear_down_live_stream` directly
        # and needs no front-door-specific awareness of its own.
        await coordinator.stop_remote_viewing_front_door(cam_id)
        await coordinator.unregister_go2rtc_stream(cam_id)
        cam_entity = coordinator.camera_entities.get(cam_id)
        if cam_entity is not None:
            stream = getattr(cam_entity, "stream", None)
            if stream is not None:
                # Hard 5 s timeout: HA's Stream.stop() awaits the worker to
                # exit, which never happens if the worker is stuck in an
                # FFmpeg reconnect-loop against a dead URL (e.g. an expired
                # REMOTE TLS-proxy port from a session that the relay has
                # already capped). Without the timeout the entire teardown
                # blocks the next stream-on for >5 min and pre-warm appears
                # to "never start" (the stuck-warming watchdog clears it at
                # 300 s). Setting `cam_entity.stream = None` synchronously
                # afterwards is sufficient — HA's internal cleanup runs in
                # a background task once the reference is dropped.
                try:
                    await asyncio.wait_for(stream.stop(), timeout=5)
                except TimeoutError:
                    _LOGGER.warning(
                        "camera.stream.stop() for %s timed out after 5s — "
                        "force-detaching, worker will be GC'd",
                        cam_id[:8],
                    )
                except Exception as exc:
                    _LOGGER.debug(
                        "camera.stream.stop() for %s failed: %s", cam_id[:8], exc
                    )
                cam_entity.stream = None


def schedule_stream_worker_error(
    coordinator: BoschCameraCoordinator, cam_id: str, msg: str
) -> None:
    """Thread-safe entry point from the log listener. Coalesces identical
    worker-error bursts and dispatches the async handler.
    """
    # Coalesce: skip if an unhandled dispatch for this cam is already
    # in flight. Prevents a flood of identical restart attempts when
    # HA's auto-restart loop fires 5-6 times per minute.
    pending = getattr(coordinator, "stream_worker_dispatch_pending", None)
    if pending is None:
        coordinator.stream_worker_dispatch_pending = pending = set()
    if cam_id in pending:
        return
    pending.add(cam_id)
    coordinator.hass.async_create_task(
        coordinator.handle_stream_worker_error(cam_id, msg)
    )


async def handle_stream_worker_error(
    coordinator: BoschCameraCoordinator, cam_id: str, msg: str
) -> None:
    """React to an HA stream-worker error for one camera.

    The primary failure mode this targets is the cycle reported in
    issue #6: the stream briefly becomes available (~2 s), FFmpeg fails,
    HA auto-restarts after a backoff, briefly becomes available again —
    forever. Each worker crash logs "Error from stream worker" exactly
    once, so our counter increments once per cycle.

    After `max_stream_errors` cycles we escalate: if the active connection
    is LOCAL we force a REMOTE restart (matches the watchdog's escalation
    path). If the active connection is already REMOTE there's no fallback
    left, so we just keep counting and let HA's internal backoff keep
    retrying — the error entries in the HA log are the diagnostic trail
    for any future debugging.

    Exception: HTTP 401 errors trigger the LOCAL rescue path *immediately*
    without waiting for the threshold. 401 is an unambiguous "Bosch
    rotated the session creds" signal — there is no value in burning
    4 additional retry cycles before re-issuing PUT /connection. Each
    retry just hits 401 again, and HA's stream component coalesces
    repeated identical errors so the counter may never reach the
    threshold (live bug 2026-05-27, Indoor Gen2: 4 errors, threshold 5,
    rescue never fired, frozen image until manual restart).
    """
    pending = getattr(coordinator, "stream_worker_dispatch_pending", None)
    try:
        coordinator.record_stream_error(cam_id)
        cfg = coordinator.get_model_config(cam_id)
        live = coordinator.live_connections.get(cam_id, {})
        conn_type = live.get("_connection_type")

        # ── LOCAL rescue: HTTP 401 means Bosch rotated session creds ──
        # When the HLS consumer disconnects (browser tab closed) and HA
        # later reconnects, the camera has silently invalidated the
        # per-session digest creds and answers 401. The fix is not to
        # fall back to REMOTE — the LAN is fine — but to issue a fresh
        # PUT /connection LOCAL and use the new creds. We allow this
        # rescue once per failure burst (reset on stream success); if the
        # rescue itself fails or the next session also gets 401, the
        # counter blocks a second attempt and the normal REMOTE fallback
        # below takes over — preventing a re-issue loop on real LAN faults.
        is_auth_error = (
            "401" in msg or "Unauthorized" in msg or "authorization failed" in msg
        )

        # Threshold guard — but 401 bypasses it (see docstring).
        if (
            not is_auth_error
            and coordinator.stream_error_count.get(cam_id, 0) < cfg.max_stream_errors
        ):
            return  # below threshold — let HA's auto-restart keep trying
        # Time-decay the rescue counter: rescues older than 5 min belong
        # to a previous failure burst. Without this the counter sticks at
        # 1 (record_stream_success never fires when no HLS consumer is
        # connected) and the next legitimate 401 burst — typically 8–14
        # min later when Bosch rotates again — skips straight to REMOTE.
        _local_rescue_ttl_sec = 300
        now_mono = time.monotonic()
        last_rescue = coordinator.local_rescue_at.get(cam_id, float("-inf"))
        if (
            last_rescue > float("-inf")
            and (now_mono - last_rescue) > _local_rescue_ttl_sec
        ):
            coordinator.local_rescue_attempts.pop(cam_id, None)
            coordinator.local_rescue_at.pop(cam_id, None)
        if (
            conn_type == "LOCAL"
            and is_auth_error
            and coordinator.local_rescue_attempts.get(cam_id, 0) < 1
        ):
            # Claim the rescue burst (one per cam at a time; decays after
            # _local_rescue_ttl_sec). The burst itself retries internally.
            coordinator.local_rescue_attempts[cam_id] = 1
            coordinator.local_rescue_at[cam_id] = now_mono
            _LOGGER.warning(
                "Stream worker auth-failed for %s on LOCAL — Bosch session "
                "creds rotated; re-issuing fresh LOCAL session (LAN preserved)",
                cam_id[:8],
            )
            # Reset error counter so try_live_connection picks LOCAL again
            # (it filters LOCAL out once the counter is saturated).
            coordinator.stream_error_count[cam_id] = 0
            coordinator.stream_fell_back.pop(cam_id, None)
            coordinator.live_connections.pop(cam_id, None)
            # Resilient rescue: a fresh PUT /connection can briefly race the
            # camera's own session teardown — observed live 2026-05-31 (Indoor
            # Gen2): the new TLS proxy got "SSL UNEXPECTED_EOF" / "Connection
            # reset by peer" on the first re-issue while the camera was
            # mid-rotation. A SINGLE attempt then left go2rtc + HA Stream
            # pinned to the dead proxy port, so consumers saw "connection
            # refused" / "wrong user/pass" → frozen image until a manual
            # integration reload. Because the rescue tears the stream down,
            # no NEW stream-worker error fires to retrigger us — so the burst
            # must self-retry with backoff instead of relying on another
            # error to drive attempt 2.
            _local_rescue_max_attempts = 3
            _local_rescue_retry_delay = 5
            result = None
            for rescue_try in range(1, _local_rescue_max_attempts + 1):
                # force_reset: stop-old-proxy + rebuild happen atomically
                # under the stream lock (no external _stop_tls_proxy that
                # could race a concurrent renewal — 2026-06-01).
                result = await coordinator.try_live_connection(cam_id, force_reset=True)
                if result:
                    _LOGGER.info(
                        "LOCAL rescue: %s restarted as %s (attempt %d/%d)",
                        cam_id[:8],
                        result.get("_connection_type", "?"),
                        rescue_try,
                        _local_rescue_max_attempts,
                    )
                    break
                if rescue_try < _local_rescue_max_attempts:
                    _LOGGER.warning(
                        "LOCAL rescue attempt %d/%d failed for %s — camera "
                        "transiently unreachable; retrying in %ds",
                        rescue_try,
                        _local_rescue_max_attempts,
                        cam_id[:8],
                        _local_rescue_retry_delay,
                    )
                    await asyncio.sleep(_local_rescue_retry_delay)
                else:
                    _LOGGER.warning(
                        "LOCAL rescue exhausted %d attempts for %s — leaving "
                        "to health watchdog / next failure burst",
                        _local_rescue_max_attempts,
                        cam_id[:8],
                    )
            return  # whatever try_live_connection produced is the new state

        if conn_type != "LOCAL":
            # Already on REMOTE (or no live session) — nothing to escalate
            # to. Counter stays saturated so a future LOCAL attempt would
            # skip straight to REMOTE.
            _LOGGER.warning(
                "Stream worker errors still occurring for %s on %s — "
                "HA backoff continues, no further fallback available",
                cam_id[:8],
                conn_type or "(no session)",
            )
            return
        _LOGGER.warning(
            "Stream worker errors exceed threshold for %s on LOCAL — "
            "tearing down and retrying (REMOTE will be selected)",
            cam_id[:8],
        )
        # Mark fallback BEFORE the rebuild so try_live_connection picks
        # REMOTE. force_reset stops the dead LOCAL proxy + clears live state
        # INSIDE the stream lock — same atomic teardown as the 401 rescue, so
        # this escalation can't race a concurrent renewal either (2026-06-01).
        coordinator.stream_fell_back[cam_id] = True
        result = await coordinator.try_live_connection(cam_id, force_reset=True)
        if result:
            _LOGGER.info(
                "Stream worker error recovery: %s restarted as %s",
                cam_id[:8],
                result.get("_connection_type", "?"),
            )
    finally:
        if pending is not None:
            pending.discard(cam_id)


async def go2rtc_consumer_count(
    coordinator: BoschCameraCoordinator, cam_id: str
) -> int | None:
    """Best-effort count of active go2rtc consumers for this camera's stream.

    go2rtc tracks every reader (WebRTC, RTSP, MSE) of a registered stream
    in `consumers`. Returns the count, or None when go2rtc cannot be
    reached on any known port (HA-bundled 11984 / legacy 1984) — None means
    "unknown", which the idle reaper treats as "no confirmed consumer".
    """
    cam_entity = coordinator.camera_entities.get(cam_id)
    if cam_entity is not None and cam_entity.entity_id:
        stream_name = cam_entity.entity_id
    else:
        stream_name = f"bosch_shc_cam_{cam_id.lower()}"
    for url in (
        "http://localhost:11984/api/streams",
        "http://localhost:1984/api/streams",
    ):
        try:
            async with asyncio.timeout(3):
                async with _go2rtc_client_session(coordinator) as s:
                    async with s.get(url, params={"src": stream_name}) as resp:
                        if resp.status != 200:
                            continue
                        data = await resp.json(content_type=None)
        except TimeoutError, aiohttp.ClientError, ValueError, RuntimeError:
            # RuntimeError: the shared go2rtc session (or its connector)
            # can be mid-close/closed if this call raced coordinator
            # teardown — treat exactly like an unreachable endpoint.
            continue
        consumers = data.get("consumers") if isinstance(data, dict) else None
        return len(consumers) if isinstance(consumers, list) else 0
    return None


async def has_active_consumer(coordinator: BoschCameraCoordinator, cam_id: str) -> bool:
    """True if anything is actively consuming the live stream.

    Three signals, in cheap-to-expensive order:
      1. An active Mini-NVR recorder — it reads the TLS proxy DIRECTLY (not
         via HLS/go2rtc, see _nvr_processes), so it must be checked
         explicitly or the reaper would tear a recording's session down.
      2. A live HLS viewer — a playlist/segment was fetched within
         STREAM_HLS_FRESH_SEC (clients refetch every few seconds; tracked by
         cf_unbuffer). HA's `Stream.available` is deliberately NOT used: it
         means "can serve", not "is serving", and stays True for the whole
         session once HLS was ever requested — which pinned a long-abandoned
         session as "watched" and stopped the reaper from ever firing (live
         bug found 2026-06-03, HLS/mobile session never reaped).
      3. go2rtc reporting ≥1 consumer (WebRTC / RTSP / MSE).

    Used by the idle reaper to avoid tearing down a session that someone —
    a viewer or an automation — is still using.
    """
    from .cf_unbuffer import hls_access_age

    if cam_id in coordinator.nvr_processes:
        return True
    cam_entity = coordinator.camera_entities.get(cam_id)
    stream = getattr(cam_entity, "stream", None) if cam_entity is not None else None
    token = getattr(stream, "access_token", None) if stream is not None else None
    if token:
        age = hls_access_age(token)
        if age is not None and age < STREAM_HLS_FRESH_SEC:
            return True
    # An external recorder (Frigate/BlueIris) connected to the persistent
    # front-door is a real consumer the reaper must not tear down.
    if (
        coordinator.frigate_runner is not None
        and coordinator.frigate_runner.active_count(cam_id) > 0
    ):
        return True
    count = await coordinator.go2rtc_consumer_count(cam_id)
    # None == go2rtc could not be reached on ANY known port (11984/1984) →
    # we CANNOT confirm the session is idle. Treating that "unknown" as
    # "no consumer" tore down LIVE viewers on any setup where go2rtc answers
    # on a different port — the WebRTC consumer is real but invisible to us,
    # so the reaper killed the stream every grace window (the user's "stream
    # just dies"). A lingering ghost while go2rtc is unreachable is far less
    # harmful than reaping an active live view, so unknown ⇒ keep alive.
    # Only a CONFIRMED count of 0 permits reaping. 2026-06-03 reaper fix.
    if count is None:
        return True
    return count > 0


async def idle_session_reaper(
    coordinator: BoschCameraCoordinator, cam_id: str, generation: int
) -> None:
    """Tear down a LOCAL session once nobody is consuming it.

    A live session — opened by a card view, a Cast, camera.play_stream,
    camera.record or a media-browser preview — keeps the camera's LOCAL
    RTSP session alive through the keepalive loop until the
    maxSessionDuration recycle (effectively forever). When the consumer
    goes away (browser tab closed / navigated away / Cast stopped) nothing
    ends it: the live-stream switch stays where it was and the camera stays
    occupied — the "ghost" session. This reaper polls every
    STREAM_IDLE_REAP_CHECK_SEC and, once there has been no consumer for
    STREAM_IDLE_REAP_SEC, runs the shared teardown so the camera drops its
    session (LED off) and the switch flips OFF.

    Reaping is driven purely by consumer presence, NOT by the switch state.
    Anything actually using the stream — a viewer (HLS/WebRTC) or an
    automation (Mini-NVR recording, Cast) — counts as a consumer
    (`_has_active_consumer`) and keeps the session alive, so automations
    that rely on the stream are unaffected. A switch that is ON but that
    nobody is watching is itself the ghost and gets reaped. Generation-
    tracked exactly like `_auto_renew_local_session`: an OFF→ON cycle or
    full renewal bumps the generation and this loop exits.
    """
    coordinator.get_session(cam_id).idle_since = None
    try:
        while True:
            await asyncio.sleep(STREAM_IDLE_REAP_CHECK_SEC)
            if coordinator.get_session(cam_id).generation != generation:
                _LOGGER.debug("Idle reaper: %s — stale generation, exiting", cam_id[:8])
                return  # OFF→ON / renewal started a newer session
            live = coordinator.live_connections.get(cam_id)
            if not live:
                _LOGGER.debug("Idle reaper: %s — session gone, exiting", cam_id[:8])
                return  # session gone — nothing to reap
            if live.get("_connection_type") != "LOCAL":
                _LOGGER.debug("Idle reaper: %s — no longer LOCAL, exiting", cam_id[:8])
                return  # REMOTE now — reaper only governs LOCAL sessions
            if await coordinator.has_active_consumer(cam_id):
                if coordinator.get_session(cam_id).idle_since is not None:
                    _LOGGER.debug(
                        "Idle reaper: %s — consumer back, idle timer reset",
                        cam_id[:8],
                    )
                coordinator.get_session(cam_id).idle_since = None
                continue
            now = time.monotonic()
            since = coordinator.get_session(cam_id).idle_since
            if since is None:
                coordinator.get_session(cam_id).idle_since = now
                _LOGGER.debug(
                    "Idle reaper: %s — no consumer, arming idle timer (%ds grace)",
                    cam_id[:8],
                    STREAM_IDLE_REAP_SEC,
                )
                continue
            _LOGGER.debug(
                "Idle reaper: %s — still no consumer (%.0fs/%ds)",
                cam_id[:8],
                now - since,
                STREAM_IDLE_REAP_SEC,
            )
            if now - since >= STREAM_IDLE_REAP_SEC:
                _LOGGER.info(
                    "Idle reaper: %s — no stream consumer for %.0fs — "
                    "tearing down LOCAL session",
                    cam_id[:8],
                    now - since,
                )
                coordinator.get_session(cam_id).idle_since = None
                # Schedule teardown in its own task: _tear_down_live_stream
                # cancels _reaper_tasks[cam_id] (i.e. THIS task), so awaiting
                # it directly would deliver CancelledError mid-teardown. A
                # fresh task runs teardown to completion; cancelling this
                # (already-returning) reaper is then a no-op.
                coordinator.hass.async_create_task(
                    coordinator.tear_down_live_stream(
                        cam_id, expected_generation=generation
                    ),
                    f"bosch_shc_camera_reap_teardown_{cam_id[:8]}",
                )
                return
    finally:
        coordinator.get_session(cam_id).idle_since = None

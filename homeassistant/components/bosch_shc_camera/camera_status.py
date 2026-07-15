"""Parallel per-camera status-check pass.

Phase 2 step 4 of the coordinator-rewrite split (see
.claude/plans/jiggly-moseying-peacock.md, project root). Local TCP ping +
cloud `/ping`/`/commissioned` run in parallel for all cameras via
`asyncio.gather(..., return_exceptions=True)` — one camera's failure must
never abort the others.

Gating semantics are DELIBERATELY different from `event_polling.py`'s
`poll_events` (do not homogenize the two — a bug-hunt agent flagged this
explicitly during review of the event-polling extraction): there is no
single top-level "do_status" bool. Instead, each camera's own coroutine
gates itself via `coordinator.should_check_status(cam_id, now,
interval_status)` — cameras can be on different per-camera check
intervals (e.g. extended intervals for persistently-offline cameras).
Correspondingly, `poll_statuses`' returned `any_status_checked` is set
True for EVERY camera whose gather result wasn't an exception — even if
that camera's own gate skipped the actual check and returned a cached
status — NOT only on a "definitive fetch" like `poll_events`'s return
value. This is intentional: `_per_cam_status_at[cam_id]` was already
updated inside a real check, so re-deriving "was anything checked" from
`_should_check_status` again here would always read False for
extended-offline cameras (their per-cam timestamp was just set to `now`),
stalling `_last_status` forever when all cameras are persistently
offline.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import aiohttp

from .const import CLOUD_API, DEFAULT_OPTIONS

if TYPE_CHECKING:  # pragma: no cover — only for type hints
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


def _get_options(entry: Any) -> dict[str, Any]:
    """Return entry options merged with defaults.

    Deliberately NOT imported from `__init__.py`'s `get_options` — that
    would be a genuine circular import (this module is imported BY
    `__init__.py` before `get_options` is even defined in it). Same
    two-line merge, just re-implemented against the leaf `DEFAULT_OPTIONS`
    constant instead.
    """
    opts: dict[str, Any] = dict(DEFAULT_OPTIONS)
    opts.update(entry.options)
    return opts


async def _check_one_camera_status(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    now: float,
    interval_status: int,
) -> tuple[str, str]:
    """Check a single camera's status. Returns ``(cam_id, status)``."""
    if not coordinator.should_check_status(cam_id, now, interval_status):
        return (cam_id, coordinator.cached_status.get(cam_id, "UNKNOWN"))

    # Fast path: local TCP ping — if camera is reachable on LAN,
    # it's definitely ONLINE (skip cloud /commissioned call).
    if await coordinator.async_local_tcp_ping(cam_id):
        coordinator.per_cam_status_at[cam_id] = now
        coordinator.offline_since.pop(cam_id, None)  # clear offline tracking
        _LOGGER.debug(
            "Local TCP ping OK for %s — ONLINE (cloud check skipped)",
            cam_id[:8],
        )
        # Active LOCAL promotion: if this cam is currently pinned to
        # REMOTE because of a past LAN-fail burst (auto-mode
        # fallback) and the LAN is reachable again, clear the
        # error counter + fallback flag so the next stream-on
        # gets to attempt LOCAL again. If a stream is *currently*
        # running on REMOTE-fallback we additionally schedule a
        # background `try_live_connection(is_renewal=True)` —
        # the inner already runs `Stream.update_source()` after
        # pre-warm, so the live HLS session swaps from Cloud to
        # LAN with a brief (~2-3 s) re-buffer instead of
        # waiting for the user to re-toggle. Cooldown 5 min
        # prevents ping-pong if LAN flaps in/out.
        if coordinator.stream_fell_back.get(cam_id):
            # Read options fresh here: this branch only runs for a
            # camera that has fallen back to REMOTE (rare), so the
            # cost is negligible, and reading the entry's options
            # directly avoids coupling to the caller's `opts`
            # snapshot (which a caller/test may set independently of
            # the entry). Reverted a micro-opt that broke that
            # contract. 2026-06-18.
            _check_opts = _get_options(coordinator.entry)
            if _check_opts.get("stream_connection_type", "local") == "auto":
                err_count_was = coordinator.stream_error_count.get(cam_id, 0)
                _LOGGER.info(
                    "AUTO mode: %s LAN reachable again — clearing "
                    "REMOTE fallback flag (counter=%d)",
                    cam_id[:8],
                    err_count_was,
                )
                coordinator.stream_error_count.pop(cam_id, None)
                coordinator.stream_error_at.pop(cam_id, None)
                coordinator.stream_fell_back.pop(cam_id, None)
                # Active promotion path: only when a stream is
                # actively running on REMOTE-fallback.
                live = coordinator.live_connections.get(cam_id, {})
                if live.get("_connection_type") == "REMOTE":
                    last_promote = coordinator.local_promote_at.get(
                        cam_id, float("-inf")
                    )
                    _LOCAL_PROMOTE_COOLDOWN_S = 300
                    if (now - last_promote) > _LOCAL_PROMOTE_COOLDOWN_S:
                        coordinator.local_promote_at[cam_id] = now
                        _LOGGER.info(
                            "AUTO mode: %s active REMOTE stream — "
                            "attempting live LOCAL promotion via renewal",
                            cam_id[:8],
                        )
                        coordinator.spawn_tracked(
                            coordinator.promote_to_local(cam_id),
                            name=f"bosch_shc_camera_promote_local_{cam_id[:8]}",
                        )
        return (cam_id, "ONLINE")

    # Cloud path: /ping (primary, 8 bytes) + /commissioned (fallback)
    status = "UNKNOWN"
    ping_ok = False
    try:
        async with asyncio.timeout(5):
            async with session.get(
                f"{CLOUD_API}/v11/video_inputs/{cam_id}/ping",
                headers=headers,
            ) as pr:
                if pr.status == 200:
                    ping_result = (await pr.text()).strip().strip('"')
                    # Map firmware update statuses to UPDATING
                    if ping_result.startswith("UPDATING"):
                        status = "UPDATING"
                    else:
                        status = ping_result  # "ONLINE" or "OFFLINE"
                    ping_ok = True
                elif pr.status == 444:
                    _LOGGER.warning(
                        "Bosch session-quota hit for %s — too many simultaneous"
                        " live sessions across all clients (HA, Bosch App, ioBroker, etc.)."
                        " Close unused sessions to recover.",
                        cam_id[:8],
                    )
                    status = "SESSION_LIMIT"
                    ping_ok = True
    except (aiohttp.ClientError, TimeoutError, ValueError) as err:
        _LOGGER.debug("Ping check error for %s: %s", cam_id, err)
    if not ping_ok:
        try:
            async with asyncio.timeout(8):
                async with session.get(
                    f"{CLOUD_API}/v11/video_inputs/{cam_id}/commissioned",
                    headers=headers,
                ) as r:
                    if r.status == 200:
                        comm = await r.json()
                        coordinator.commissioned_cache[cam_id] = comm
                        if comm.get("connected") and comm.get("commissioned"):
                            status = "ONLINE"
                        elif comm.get("configured"):
                            status = "OFFLINE"
                    elif r.status == 444:
                        _LOGGER.warning(
                            "Bosch session-quota hit for %s (commissioned fallback)"
                            " — too many simultaneous live sessions across all clients.",
                            cam_id[:8],
                        )
                        status = "SESSION_LIMIT"
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            _LOGGER.debug("Commissioned fallback error for %s: %s", cam_id, err)

    coordinator.per_cam_status_at[cam_id] = now
    # Track offline duration for extended interval.
    # SESSION_LIMIT is NOT a connectivity failure — do not add to _offline_since
    # so the camera does not get penalised with extended check intervals.
    if status in ("OFFLINE", "UPDATING"):
        if cam_id not in coordinator.offline_since:
            coordinator.offline_since[cam_id] = now
    else:
        coordinator.offline_since.pop(cam_id, None)
    # Fire persistent notification if 444 hits accumulate
    if status == "SESSION_LIMIT":
        _handle_quota = getattr(coordinator, "_async_handle_session_quota_hit", None)
        if _handle_quota is not None:
            coordinator.spawn_tracked(
                _handle_quota(cam_id),
                name=f"bosch_shc_camera_session_quota_{cam_id[:8]}",
            )
    return (cam_id, status)


async def poll_statuses(
    coordinator: BoschCameraCoordinator,
    cam_ids: list[str],
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    now: float,
    opts: dict[str, Any],
) -> bool:
    """Run the parallel status-check pass across all cameras.

    Returns whether any camera's status was processed this tick (True for
    every non-exception gather result — see module docstring for why this
    differs from a "definitive fetch only" semantic).
    """
    interval_status = int(opts.get("interval_status", 60))
    status_results = await asyncio.gather(
        *[
            _check_one_camera_status(
                coordinator, cid, session, headers, now, interval_status
            )
            for cid in cam_ids
        ],
        return_exceptions=True,
    )
    any_status_checked = False
    for result in status_results:
        if isinstance(result, BaseException):
            continue
        cid, status = result
        coordinator.cached_status[cid] = status
        # Mark as checked unconditionally — _per_cam_status_at[cid] was
        # just updated inside _check_one_camera_status, so re-calling
        # _should_check_status would always return False for
        # extended-offline cams (their per-cam timestamp was just set to
        # `now`). That caused _last_status to stall forever when all
        # cameras were persistently offline, making do_status=True on
        # every subsequent tick even though no real API calls ran.
        any_status_checked = True
    return any_status_checked

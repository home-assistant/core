"""Parallel per-camera events-fetch pass.

Phase 2 step 4 of the coordinator-rewrite split (see
.claude/plans/jiggly-moseying-peacock.md, project root). Fetches
`/v11/events` for every camera in parallel via `asyncio.gather(...,
return_exceptions=True)` — one camera's failure must never abort the
others, and a transient per-camera failure must never blank that camera's
cached events (see `_fetch_one_camera_events`'s own docstring for the
`ok` flag's exact contract, carried over unchanged from the pre-extraction
inline code).

`poll_events` is gated by `do_events` exactly as the inline code was — the
gate lives in the caller-supplied bool, not recomputed here, since that
gate's computation depends on FCM-health/first-tick state that stays
inline in `_async_update_data` (not this decomposition's concern).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import aiohttp

from .const import CLOUD_API

if TYPE_CHECKING:  # pragma: no cover — only for type hints
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


async def _fetch_one_camera_events(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    session: aiohttp.ClientSession,
    headers: dict[str, str],
) -> tuple[str, list[Any], bool]:
    """Fetch events for a single camera.

    Returns ``(cam_id, events, ok)``. ``ok`` is True only when the cloud
    gave a definitive answer (last_event matched the cached id, or the
    full events list came back 200). On a transient failure ``ok`` is
    False so the caller keeps the previously-cached events instead of
    blanking them, and does not advance ``_last_events`` (which would
    defer the next retry by a full poll interval — up to 300 s while FCM
    is healthy). Mirrors the cross-version ioBroker fix.
    """
    events: list[Any] = []
    skip_full_fetch = False
    ok = False
    try:
        async with asyncio.timeout(5):
            async with session.get(
                f"{CLOUD_API}/v11/video_inputs/{cam_id}/last_event",
                headers=headers,
            ) as le_resp:
                if le_resp.status == 200:
                    last_ev = await le_resp.json()
                    last_ev_id = last_ev.get("id", "")
                    if last_ev_id and last_ev_id == coordinator._last_event_ids.get(
                        cam_id
                    ):
                        skip_full_fetch = True
                        ok = True
                        events = coordinator._cached_events.get(cam_id, [])
                        _LOGGER.debug(
                            "last_event unchanged for %s (id=%s) — skipping full fetch",
                            cam_id,
                            last_ev_id[:8],
                        )
    except Exception as err:
        _LOGGER.debug(
            "last_event check error for %s: %s — falling back to full fetch",
            cam_id,
            err,
        )

    if not skip_full_fetch:
        try:
            url = f"{CLOUD_API}/v11/events?videoInputId={cam_id}&limit=20"
            async with asyncio.timeout(15):
                async with session.get(url, headers=headers) as r:
                    if r.status == 200:
                        events = await r.json()
                        ok = True
        except Exception as err:
            _LOGGER.debug(
                "Events fetch error for %s: %s",
                cam_id,
                coordinator._err_str(err),
            )
    return (cam_id, events, ok)


async def poll_events(
    coordinator: BoschCameraCoordinator,
    cam_ids: list[str],
    session: aiohttp.ClientSession,
    headers: dict[str, str],
    do_events: bool,
) -> bool:
    """Run the parallel events-fetch pass across all cameras.

    No-op (returns False) when ``do_events`` is False — the caller decides
    whether this poll interval is due. Returns whether at least one
    camera's events were freshly (successfully) fetched this tick.
    """
    any_events_fetched = False
    if do_events:
        event_results = await asyncio.gather(
            *[
                _fetch_one_camera_events(coordinator, cid, session, headers)
                for cid in cam_ids
            ],
            return_exceptions=True,
        )
        for ev_result in event_results:
            if isinstance(ev_result, BaseException):
                continue
            cid, ev_list, ev_ok = ev_result
            # Only overwrite the cache on a definitive fetch — a transient
            # failure must not blank a camera's events (and its
            # events-today count) until the next successful poll.
            if ev_ok:
                coordinator._cached_events[cid] = ev_list
                any_events_fetched = True
    return any_events_fetched

"""Per-camera data-dict build + new-event dispatch.

Phase 2 step 5 of the coordinator-rewrite split (see
.claude/plans/jiggly-moseying-peacock.md, project root). Runs
sequentially (must stay ordered — `_last_event_ids` bookkeeping and the
polling-vs-FCM dedup logic depend on being processed one camera at a
time), unlike the parallel status/events gather passes in
`camera_status.py`/`event_polling.py`.
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING, Any

from .const import FCM_DELIVERY_DEAD_AFTER_SEC

if TYPE_CHECKING:  # pragma: no cover — only for type hints
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


async def build_data_and_dispatch(
    coordinator: BoschCameraCoordinator,
    cam_ids: list[str],
    cam_by_id: dict[str, dict[str, Any]],
    now: float,
    do_events: bool,
) -> dict[str, Any]:
    """Build the per-camera ``data`` dict and dispatch new-event alerts.

    Returns the ``data`` dict keyed by cam_id (``info``/``status``/
    ``events``/``live``), same shape `_async_update_data` has always
    returned.
    """
    data: dict[str, Any] = {}

    for cam_id in cam_ids:
        cam = cam_by_id[cam_id]
        status = coordinator.cached_status.get(cam_id, "UNKNOWN")
        events = coordinator.cached_events.get(cam_id, [])

        if do_events and events:
            newest_id = events[0].get("id", "")
            prev_id = coordinator.last_event_ids.get(cam_id)
            if prev_id is None:
                unread_ids = [
                    ev.get("id")
                    for ev in events
                    if ev.get("id") and not ev.get("isRead", False)
                ]
                if unread_ids and coordinator.options.get("mark_events_read", False):
                    _LOGGER.debug(
                        "Startup: marking %d unread event(s) as read for %s",
                        len(unread_ids),
                        cam_id,
                    )
                    try:
                        await coordinator.async_mark_events_read(unread_ids)
                    except asyncio.CancelledError:
                        raise
                    except Exception as err:
                        _LOGGER.debug(
                            "Mark-read (startup) failed for %s: %s", cam_id, err
                        )
                # Bootstrap _last_event_ids so the next polling tick can
                # detect newer events. Without this seed, prev_id stays
                # None forever in polling-only mode (no FCM) — every
                # tick re-enters this branch, alert chain (`elif newest_id
                # and newest_id != prev_id`) is never reached, and
                # automations on `bosch_shc_camera_motion` never fire
                # after a restart. (Forum: geotie 2026 — "Automation
                # funktioniert, wird aber oft nicht ausgelöst".)
                if newest_id:
                    coordinator.last_event_ids[cam_id] = newest_id
            elif newest_id and newest_id != prev_id:
                # Per-event-ID dedup shared with fcm.async_handle_fcm_push.
                # Guards against a polling tick firing an alert that the
                # FCM handler already dispatched for the same event ID.
                _now_mono = time.monotonic()
                # Delivery-death detection (issue #36): this poll found a
                # genuinely new event. If FCM push is enabled+running+
                # "healthy" yet no real push has arrived in the last
                # FCM_DELIVERY_DEAD_AFTER_SEC, push delivery is dead at the
                # cloud/Google layer even though the socket reports
                # is_started()=True — the poll just proved push missed a
                # real event. Flag unhealthy + force a HARD heal (purge +
                # fresh registration, which re-POSTs to Bosch /v11/devices).
                # A push arriving just before this poll keeps _fcm_last_push
                # recent → no false positive.
                with coordinator.fcm_lock:
                    _last_push = getattr(coordinator, "fcm_last_push", float("-inf"))
                    _started_at = getattr(coordinator, "fcm_started_at", float("-inf"))
                    # Grace reference: the later of "last real push" and
                    # "listener start". A still-warming-up listener (no
                    # push yet, started <window ago) is never condemned;
                    # a dead-from-start registration IS caught once the
                    # listener has been up for the window with no push.
                    _ref = max(_last_push, _started_at)
                    _push_age = _now_mono - _ref
                    if (
                        coordinator.options.get("enable_fcm_push", False)
                        and getattr(coordinator, "fcm_running", False)
                        and getattr(coordinator, "fcm_healthy", False)
                        and _ref != float("-inf")
                        and _push_age > FCM_DELIVERY_DEAD_AFTER_SEC
                    ):
                        coordinator.fcm_healthy = False
                        coordinator.fcm_force_hard_heal = True
                        _ago = (
                            "never"
                            if _last_push == float("-inf")
                            else f"{_push_age / 60.0:.0f} min ago"
                        )
                        _LOGGER.warning(
                            "FCM delivery watchdog: polling found a new event "
                            "(%s) that push never delivered (last push %s) — "
                            "delivery is dead despite a live socket; forcing "
                            "fresh registration with Bosch CBS",
                            newest_id,
                            _ago,
                        )
                _dedup_skip = (
                    coordinator.alert_sent_ids.get(newest_id, float("-inf"))
                    > _now_mono - 60.0
                )
                coordinator.last_event_ids[cam_id] = newest_id
                if _dedup_skip:
                    _LOGGER.debug(
                        "Polling dedup: skipping duplicate alert for %s id=%s",
                        cam_id,
                        newest_id,
                    )
                else:
                    coordinator.alert_sent_ids[newest_id] = _now_mono
                    # Bound memory: the FCM handler prunes this dedup map
                    # too, but it never runs when FCM is disabled, so the
                    # polling path must prune here as well — otherwise it
                    # grows one entry per event forever. Drop entries older
                    # than 2× the 60s dedup window.
                    if len(coordinator.alert_sent_ids) > 64:
                        # Mutate in place — a dict-comprehension rebind
                        # (coordinator.alert_sent_ids = {...}) would detach
                        # any alias another concurrent call already
                        # holds. fcm.py's async_handle_fcm_push does
                        # exactly that: it captures `_sent =
                        # coordinator.alert_sent_ids` once, then
                        # writes to it later after an await. If this
                        # rebind ran in between, that later write would
                        # land in the orphaned old dict — invisible to
                        # any later reader of coordinator.alert_sent_ids —
                        # allowing a duplicate alert for the same event
                        # (bug-hunt 2026-07-03).
                        _cutoff = _now_mono - 120.0
                        for _k in [
                            k
                            for k, v in coordinator.alert_sent_ids.items()
                            if v < _cutoff
                        ]:
                            del coordinator.alert_sent_ids[_k]
                    _LOGGER.debug(
                        "New event detected for %s (id=%s) — triggering snapshot refresh",
                        cam_id,
                        newest_id,
                    )
                    cam_entity = coordinator.camera_entities.get(cam_id)
                    if cam_entity:
                        coordinator.spawn_tracked(
                            cam_entity.async_trigger_image_refresh(delay=2),
                            name=f"bosch_shc_camera_image_refresh_{cam_id[:8]}",
                        )
                    newest_event = events[0]
                    event_type = newest_event.get("eventType", "")
                    event_tags = newest_event.get("eventTags", []) or []
                    # Gen2 DualRadar fires eventType=MOVEMENT w/ eventTags=["PERSON"]
                    # when a human is detected — the tag is more specific, so upgrade.
                    if "PERSON" in event_tags and event_type == "MOVEMENT":
                        event_type = "PERSON"
                    cam_name = cam.get("title", cam_id)
                    event_payload = {
                        "camera_id": cam_id,
                        "camera_name": cam_name,
                        "timestamp": newest_event.get("timestamp", ""),
                        "image_url": newest_event.get("imageUrl", ""),
                        "event_id": newest_id,
                    }
                    if event_type == "MOVEMENT":
                        coordinator.hass.bus.async_fire(
                            "bosch_shc_camera_motion", event_payload
                        )
                    elif event_type == "AUDIO_ALARM":
                        coordinator.hass.bus.async_fire(
                            "bosch_shc_camera_audio_alarm", event_payload
                        )
                    elif event_type == "PERSON":
                        coordinator.hass.bus.async_fire(
                            "bosch_shc_camera_person", event_payload
                        )
                    coordinator.spawn_tracked(
                        coordinator.async_send_alert(
                            cam_name,
                            event_type,
                            newest_event.get("timestamp", ""),
                            newest_event.get("imageUrl", ""),
                            newest_event.get("videoClipUrl", ""),
                            newest_event.get("videoClipUploadStatus", ""),
                            event_id=newest_id,
                        ),
                        name=f"bosch_shc_camera_send_alert_{cam_id[:8]}",
                    )
                    if coordinator.options.get("mark_events_read", False):
                        try:
                            await coordinator.async_mark_events_read([newest_id])
                        except asyncio.CancelledError:
                            raise
                        except Exception as err:
                            _LOGGER.debug(
                                "Mark-read (new event) failed for %s: %s",
                                cam_id,
                                err,
                            )
            elif newest_id:
                coordinator.last_event_ids[cam_id] = newest_id

        data[cam_id] = {
            "info": cam,
            "status": status,
            "events": events,
            "live": coordinator.live_connections.get(cam_id, {}),
        }

    return data

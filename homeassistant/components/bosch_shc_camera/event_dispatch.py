"""Per-camera data-dict build + new-event dispatch.

Runs sequentially (must stay ordered — `last_event_ids` bookkeeping depends
on being processed one camera at a time), unlike the parallel status/events
gather passes in `camera_status.py`/`event_polling.py`.

Public event API: this integration deliberately exposes no binary_sensor
(or other) platform in its reduced, snapshot-only scope, so the three HA
bus events fired by `_dispatch_new_event` — ``bosch_shc_camera_motion``,
``bosch_shc_camera_person``, ``bosch_shc_camera_audio_alarm`` — are the
only mechanism by which an automation can react to a motion/person/audio
event; they are supported, stable functionality (payload:
``camera_id``/``camera_name``/``timestamp``/``image_url``/``event_id``),
not incidental internals (Copilot review round 7).
"""

import logging
import math
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover — only for type hints
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


def _dispatch_new_event(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    cam: dict[str, Any],
    events: list[dict[str, Any]],
    newest_id: str,
) -> None:
    """Handle a newest-event-changed transition: dedup, fire bus event, refresh."""
    now_mono = time.monotonic()
    dedup_skip = coordinator.alert_sent_ids.get(newest_id, -math.inf) > now_mono - 60.0
    coordinator.last_event_ids[cam_id] = newest_id
    if dedup_skip:
        _LOGGER.debug(
            "Polling dedup: skipping duplicate alert for %s id=%s", cam_id, newest_id
        )
        return

    coordinator.alert_sent_ids[newest_id] = now_mono
    _prune_alert_sent_ids(coordinator, now_mono)
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
    # Gen2 DualRadar fires eventType=MOVEMENT w/ eventTags=["PERSON"] when a
    # human is detected — the tag is more specific, so upgrade.
    if "PERSON" in event_tags and event_type == "MOVEMENT":
        event_type = "PERSON"
    event_payload = {
        "camera_id": cam_id,
        "camera_name": cam.get("title", cam_id),
        "timestamp": newest_event.get("timestamp", ""),
        "image_url": newest_event.get("imageUrl", ""),
        "event_id": newest_id,
    }
    bus_event = {
        "MOVEMENT": "bosch_shc_camera_motion",
        "AUDIO_ALARM": "bosch_shc_camera_audio_alarm",
        "PERSON": "bosch_shc_camera_person",
    }.get(event_type)
    if bus_event:
        coordinator.hass.bus.async_fire(bus_event, event_payload)


def _prune_alert_sent_ids(coordinator: BoschCameraCoordinator, now_mono: float) -> None:
    """Bound `alert_sent_ids` memory once it grows past 64 entries.

    The FCM handler prunes this dedup map too, but it never runs when FCM is
    disabled, so the polling path must prune here as well — otherwise it
    grows one entry per event forever. Drop entries older than 2x the 60s
    dedup window.
    """
    if len(coordinator.alert_sent_ids) <= 64:
        return
    # Mutate in place, not a dict-comprehension rebind — a rebind would
    # detach any alias another concurrent call already holds (bug-hunt
    # 2026-07-03).
    cutoff = now_mono - 120.0
    stale_ids = [k for k, v in coordinator.alert_sent_ids.items() if v < cutoff]
    for stale_id in stale_ids:
        del coordinator.alert_sent_ids[stale_id]


async def build_data_and_dispatch(
    coordinator: BoschCameraCoordinator,
    cam_ids: list[str],
    cam_by_id: dict[str, dict[str, Any]],
    now: float,
    do_events: bool,
) -> dict[str, Any]:
    """Build the per-camera ``data`` dict and dispatch new-event alerts.

    Returns the ``data`` dict keyed by cam_id (``info``/``status``/
    ``events``), same shape `_async_update_data` has always returned.
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
                # Bootstrap last_event_ids so the next polling tick can
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
                _dispatch_new_event(coordinator, cam_id, cam, events, newest_id)
            elif newest_id:
                coordinator.last_event_ids[cam_id] = newest_id

        data[cam_id] = {
            "info": cam,
            "status": status,
            "events": events,
        }

    return data

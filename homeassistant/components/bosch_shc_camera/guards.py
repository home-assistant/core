"""Shared hardware-generation and privacy-mode guard utilities.

These helpers are used across multiple entity platforms (switch, number, select,
light). Extracted from switch.py to break the import cycle where those modules
imported from switch at function-call time.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

_GEN2_INDOOR_HW = {"HOME_Eyes_Indoor", "CAMERA_INDOOR_GEN2"}
_INDOOR_HW = {"INDOOR", "CAMERA_360", "HOME_Eyes_Indoor", "CAMERA_INDOOR_GEN2"}


def _get_cam_lock(coordinator: Any, lock_attr: str, cam_id: str) -> asyncio.Lock:
    """Return (lazily creating) a per-camera asyncio.Lock stored on the
    coordinator under ``lock_attr``, keyed by ``cam_id``.

    Several entity classes across switch.py/number.py/light.py can share one
    Bosch cloud endpoint that requires a full-body PUT (multiple sibling
    fields in one object — e.g. audioEnabled+speakerLevel+microphoneLevel on
    /audio). Concurrent read-modify-write calls for two different fields on
    the SAME endpoint must serialize on the SAME lock instance and merge only
    their own field back into the shared cache afterward, or one write's
    stale snapshot can silently revert the other's just-written field.
    """
    locks: dict[str, asyncio.Lock] | None = getattr(coordinator, lock_attr, None)
    if locks is None:
        locks = {}
        setattr(coordinator, lock_attr, locks)
    lock = locks.get(cam_id)
    if lock is None:
        lock = asyncio.Lock()
        locks[cam_id] = lock
    return lock


def _is_gen2_indoor(entity: Any) -> bool:
    """Return True if the entity's camera is a Gen2 Indoor model."""
    hw = (
        entity.coordinator.data.get(entity._cam_id, {})
        .get("info", {})
        .get("hardwareVersion", "")
    )
    return hw in _GEN2_INDOOR_HW


async def _warn_if_privacy_on(entity: Any, feature_name: str) -> bool:
    """Show a persistent notification when the user tries to change a
    privacy-gated setting while privacy mode is ON. Returns True if the
    write was blocked.

    The Bosch cloud API returns HTTP 443 "sh:camera.in.privacy.mode" on
    reads and writes to /intrusionDetectionConfig, /zones, /privateAreas,
    /motion, and some lighting endpoints while the camera is in privacy
    mode. Without a guard the write silently fails in the logs; with this
    guard the user sees a clear notification explaining why.
    """
    coordinator = entity.coordinator
    cam_id = entity._cam_id
    cache = coordinator.shc_state_cache.get(cam_id, {})
    privacy_on = bool(cache.get("privacy_mode"))
    if not privacy_on:
        return False
    cam_title = coordinator.data.get(cam_id, {}).get("info", {}).get("title", cam_id)
    _LOGGER.warning(
        "%s write blocked for %s — camera is in privacy mode (HTTP 443 would follow).",
        feature_name,
        cam_title,
    )
    try:
        await entity.hass.services.async_call(
            "persistent_notification",
            "create",
            {
                "title": f"{feature_name} — Kamera im Privacy-Mode",
                "message": (
                    f"Die Einstellung **{feature_name}** für **{cam_title}** kann nicht "
                    f"geändert werden, solange der Privacy-Mode aktiv ist.\n\n"
                    f"Die Kamera liefert in diesem Zustand `HTTP 443 sh:camera.in.privacy.mode` "
                    f"auf Schreibzugriffe. Schalte zuerst den Privacy-Mode aus "
                    f"(`switch.bosch_{cam_title.lower()}_privacy_mode`) und versuche es erneut."
                ),
                "notification_id": f"bosch_privacy_blocked_{cam_id}",
            },
            blocking=False,
        )
    except Exception as err:  # noqa: BLE001 — best-effort UI notification for a write already blocked; the service call target/schema is arbitrary HA core plumbing and must never mask the privacy-mode-blocked result being returned below
        _LOGGER.debug("persistent_notification create failed: %s", err)
    return True

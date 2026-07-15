"""Bosch Smart Home Camera — Snapshot Persistence.

Async-safe disk helpers to persist the latest JPEG snapshot per camera across
HA restarts. Stored in .storage/bosch_shc_camera/snapshots/{cam_id}.jpg.

All blocking I/O is wrapped in hass.async_add_executor_job so the event loop
is never blocked. Writes are atomic: a temp file is written first, then
renamed to the final path so a crash mid-write leaves the previous file intact.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import re

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Per-camera lock so two concurrent save_snapshot() calls for the SAME camera
# (e.g. a coordinator tick and an FCM-push handler both fetching+saving around
# the same time) can't race on the shared .tmp path. hass.async_add_executor_job
# runs on a real ThreadPoolExecutor thread, not just an interleaved coroutine,
# so without this lock two threads could genuinely write the fixed
# `{cam_id}.jpg.tmp` path concurrently — at best "last replace() wins" with no
# ordering guarantee (an older frame could clobber a newer one), at worst a
# corrupted .tmp if the writes overlap (bug-hunt 2026-07-03).
_save_locks: dict[str, asyncio.Lock] = {}


def _get_save_lock(cam_id: str) -> asyncio.Lock:
    lock = _save_locks.get(cam_id)
    if lock is None:
        lock = asyncio.Lock()
        _save_locks[cam_id] = lock
    return lock


# Bosch camera IDs are UUID-formatted: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
# Normalized to upper-case before matching (API returns upper-case; callers may
# pass lower-case e.g. after slug munging — both are accepted, stored upper-case).
_CAM_ID_RE = re.compile(
    r"^[A-F0-9]{8}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{12}$"
)

# Sanity bounds for snapshot byte sizes.
# Bosch snapshots are 50–800 KiB typically; 100 B is the smallest valid JPEG.
_MIN_JPEG_BYTES = 100
_MAX_JPEG_BYTES = 10 * 1024 * 1024  # 10 MiB hard cap


def _validate_cam_id(cam_id: str) -> str:
    """Validate *cam_id* and return its upper-case normalised form.

    Raises ValueError when *cam_id* is not a valid Bosch UUID (prevents
    path-traversal attacks via crafted cam_id values like '../../etc/passwd').
    Both upper- and lower-case hex digits are accepted; the return value is
    always upper-case so storage keys are consistent.
    """
    normalised = cam_id.upper()
    if not _CAM_ID_RE.match(normalised):
        raise ValueError(
            f"cam_id must match ^[A-F0-9-]{{36}}$ (UUID format), got: {cam_id!r}"
        )
    return normalised


def _storage_dir(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(".storage")) / "bosch_shc_camera" / "snapshots"


def _snap_path(hass: HomeAssistant, cam_id: str) -> Path:
    return _storage_dir(hass) / f"{cam_id}.jpg"


def _sync_save(hass: HomeAssistant, cam_id: str, jpeg: bytes) -> None:
    """Blocking: atomically write *jpeg* to the snapshot store.

    Called via async_add_executor_job — never call directly from async code.

    The write is two-phase (write .tmp → rename to .jpg) so a crash between
    the two steps leaves the previous .jpg intact.  If the rename fails (e.g.
    cross-device rename on NFS/Docker bind-mounts) the .tmp is cleaned up in
    the finally block so it does not accumulate across restarts.
    """
    snap_dir = _storage_dir(hass)
    snap_dir.mkdir(parents=True, exist_ok=True)
    final = snap_dir / f"{cam_id}.jpg"
    tmp = snap_dir / f"{cam_id}.jpg.tmp"
    tmp.write_bytes(jpeg)
    try:
        tmp.replace(final)
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except OSError as unlink_err:
            # Secondary failure: log but do not let it mask the original replace() error.
            _LOGGER.debug(
                "bosch_shc_camera: could not remove tmp file %s after failed replace: %s",
                tmp,
                unlink_err,
            )
        raise


def _sync_load(hass: HomeAssistant, cam_id: str) -> bytes | None:
    """Blocking: read and return persisted snapshot bytes, or None if absent.

    Called via async_add_executor_job — never call directly from async code.
    """
    snap_path = _snap_path(hass, cam_id)
    try:
        return snap_path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as err:
        _LOGGER.warning(
            "bosch_shc_camera: failed to read snapshot for %s: %s", cam_id, err
        )
        return None


async def save_snapshot(hass: HomeAssistant, cam_id: str, jpeg: bytes) -> None:
    """Async: validate and atomically persist *jpeg* for *cam_id*.

    Silently skips when:
    - *jpeg* is smaller than 100 bytes (corrupt / placeholder; benign cold-boot
      transient → DEBUG)
    - *jpeg* is larger than 10 MiB (unexpected; would waste disk I/O → WARNING)

    Raises ValueError when *cam_id* is not a valid UUID — callers must ensure
    only real Bosch camera IDs are passed (prevents path traversal).
    """
    cam_id = _validate_cam_id(cam_id)
    n = len(jpeg)
    if n < _MIN_JPEG_BYTES:
        # Benign on cold boot: the camera entity persists its ~180 B
        # _PLACEHOLDER_JPEG before the first real frame arrives. A normal
        # transient, not an anomaly → DEBUG.
        _LOGGER.debug(
            "bosch_shc_camera: snapshot for %s too small (%d B) — skipping persist",
            cam_id,
            n,
        )
        return
    if n > _MAX_JPEG_BYTES:
        _LOGGER.warning(
            "bosch_shc_camera: snapshot for %s too large (%d B > %d B) — skipping persist",
            cam_id,
            n,
            _MAX_JPEG_BYTES,
        )
        return
    async with _get_save_lock(cam_id):
        await hass.async_add_executor_job(_sync_save, hass, cam_id, jpeg)


async def load_snapshot(hass: HomeAssistant, cam_id: str) -> bytes | None:
    """Async: load persisted snapshot bytes for *cam_id*, or None if absent.

    Raises ValueError when *cam_id* is not a valid UUID.
    Returns None on FileNotFoundError; logs WARNING on other OSError.
    """
    cam_id = _validate_cam_id(cam_id)
    return await hass.async_add_executor_job(
        _sync_load, hass, cam_id
    )  # value is correct at runtime; HA/external source is Any-typed

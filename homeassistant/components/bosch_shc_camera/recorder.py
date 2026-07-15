"""Mini-NVR — local-only continuous recording sidecar.

Phase 1 MVP: spawn one ffmpeg child per LOCAL-streaming camera that reads from
the existing published RTSP URL (`_live_connections[cam_id]["rtspsUrl"]` —
since viewing_front_door.py, this is normally the credential-free stable-port
viewing front-door URL for LOCAL sessions, `rtsp://127.0.0.1:NNN/...`, falling
back to the raw `rtsp://user:pass@127.0.0.1:NNN/...` TLS-proxy URL only if the
front-door failed to bind) and segments the stream into 5-min wall-aligned MP4
files on local disk.

Constraint (LAN-only):
    The recorder is allowed to run only when the camera's live session is in
    LOCAL mode AND the camera reports ONLINE.  If either flips off (e.g. the
    LOCAL→REMOTE fallback fires, or the camera goes OFFLINE) the recorder
    stops cleanly — no fallback to the cloud relay path.  See
    `docs/mini-nvr-concept.md` §2.

Architecture choice (`docs/mini-nvr-concept.md` §10): in-integration via
`asyncio.create_subprocess_exec`.  HA Add-on path is deferred to Phase 2 if
4-cam Pi 4 setups choke.  `-c copy` only — no transcoding.
"""

from __future__ import annotations

import asyncio
import datetime
from datetime import UTC
import ftplib
import logging
import math
import os
import re
import shutil
import signal
import time
from typing import TYPE_CHECKING, Any

from .const import (
    TIMEOUT_RECORDER_FFMPEG_INIT,
    TIMEOUT_RECORDER_GRACE,
    TIMEOUT_RECORDER_KILL_WAIT,
    TIMEOUT_RECORDER_POSTROLL_GRACE,
    TIMEOUT_RECORDER_STDERR_DRAIN,
)
from .smb import _ftp_connect, _ftp_makedirs, _safe_name, smb_makedirs

if TYPE_CHECKING:  # pragma: no cover — only for type hints
    from . import BoschCameraCoordinator

_LOGGER = logging.getLogger(__name__)


# Defaults — also exposed as config-flow options (`nvr_*`).
DEFAULT_BASE_PATH = "/config/bosch_nvr"
DEFAULT_RETENTION_DAYS = 3
DEFAULT_SEGMENT_SECONDS = 300  # 5 minutes, wall-aligned
# Crash-loop guard: if ffmpeg exits twice within this window we give up.
_RESPAWN_WINDOW_SECONDS = 30.0
_RESPAWN_DELAY_SECONDS = 5.0
# Per-call deadline for the NVR SMB/FTP cleanup walk (_sync_nvr_cleanup_smb /
# _sync_nvr_cleanup_ftp): a hung/unreachable NAS share has no other backstop
# — these run in an executor thread with no depth limit and no per-op
# timeout of their own, so a stalled scandir()/LIST call could otherwise
# block the whole cleanup job (and the executor thread) indefinitely. Checked
# with time.monotonic() (SENTINEL_RULE — never 0.0) at the top of every
# recursive call; on expiry the walk unwinds without deleting further files
# rather than raising, so files already found within the deadline are still
# removed.
_NVR_CLEANUP_MAX_SECONDS = 60.0
# Auth-retry guard (issue #42 follow-up): a single 401 is almost always a
# transient heartbeat cred-rotation race and is retried without counting
# toward the crash-window give-up above — but a GENUINE broken credential
# would otherwise retry silently forever. Cap consecutive 401s so a real
# fault still surfaces instead of looping forever.
_MAX_CONSECUTIVE_AUTH_RETRIES = 5
# Stop timeout — give ffmpeg time to flush the trailing moov atom on SIGTERM.
# Centralized in const.py so the SIGTERM/SIGKILL/stderr timing is tunable
# without touching the recorder.
_STOP_GRACE_SECONDS = TIMEOUT_RECORDER_GRACE

# When the NVR switch is toggled on right after Live Stream ON, the TLS
# proxy URL is still empty until the RTSP DESCRIBE handshake completes
# (~3–10 s on Gen2). Poll for it before giving up.
_PROXY_URL_WAIT_STEPS = 24
_PROXY_URL_WAIT_INTERVAL = 0.5

# ── Phase 4: pre-roll buffer tunables ────────────────────────────────────────
_PREROLL_SEGMENT_SECONDS = 10  # short segments for fine-grained pre-roll
_PREROLL_MAX_SEGMENTS = 5  # keep last 5 × 10 s = 50 s max in tmpfs
_PREROLL_MIN_SIZE_BYTES = 1024  # discard sub-1 KB corrupt segments

# ── Staging-drain watcher tunables ───────────────────────────────────────────
# ffmpeg writes EVERY segment locally first ("staging") so a half-flushed file
# is never uploaded. Once a segment file's mtime stops changing AND it has a
# reasonable size we treat it as finalized and move it to the configured
# storage target.
_DRAIN_TICK_SECONDS = 30.0  # how often the watcher sweeps staging
_DRAIN_FINALIZE_AGE_SECONDS = 60.0  # mtime must be older than this
_DRAIN_MIN_SIZE_BYTES = 10 * 1024  # < 10 KB → still being written / corrupt
_DRAIN_MAX_RETRIES = 5  # quarantine after this many failed uploads
_STAGING_DIRNAME = "_staging"
_FAILED_DIRNAME = "_failed"


# ── pure helpers (testable without spawning ffmpeg or touching disk) ─────────


def _segment_dir(base_path: str, cam_name: str) -> str:
    """Return ``{base_path}/{sanitized_cam_name}``.

    Camera names are user-controlled (Bosch app title), so we run them through
    the same `_safe_name()` used by the SMB upload pipeline to strip path
    traversal and shell metacharacters.  Test: `tests/test_recorder.py`.
    """
    return os.path.join(base_path, _safe_name(cam_name))


def _segment_pattern(base_path: str, cam_name: str) -> str:
    """Return the strftime pattern for the *promoted* (post-drain) segments.

    Layout: ``{base}/{cam}/YYYY-MM-DD/HH-MM.mp4``. This is where files end up
    when ``nvr_storage_target == "local"``. Wall-aligned 5 min slices make
    timeline scrubbing intuitive — "show me 14:35" doesn't fall inside a
    segment that started at 14:32. Used by the daily retention purge for the
    LOCAL target and as the canonical browse path for Media Source.
    """
    cam_dir = _segment_dir(base_path, cam_name)
    return os.path.join(cam_dir, "%Y-%m-%d", "%H-%M.mp4")


def _staging_dir(base_path: str, cam_name: str) -> str:
    """Return the per-camera staging dir under ``{base}/_staging/{cam}/``.

    ffmpeg always writes here regardless of ``nvr_storage_target``. Defends
    against partial-writes during segment rotation: an upload that happens
    mid-flush would otherwise produce a truncated MP4 with a missing moov
    atom. The drain watcher (``_drain_staging_to_remote``) picks up files
    only after their mtime has stopped moving, guaranteeing they are complete.
    """
    return os.path.join(base_path, _STAGING_DIRNAME, _safe_name(cam_name))


def _staging_pattern(base_path: str, cam_name: str) -> str:
    """Ffmpeg ``-strftime`` output template inside the staging tree."""
    return os.path.join(
        _staging_dir(base_path, cam_name),
        "%Y-%m-%d",
        "%H-%M.mp4",
    )


def _failed_dir(base_path: str, cam_name: str) -> str:
    """Quarantine dir for files that exceeded the upload retry cap."""
    return os.path.join(base_path, _FAILED_DIRNAME, _safe_name(cam_name))


def _remote_smb_path(opts: dict[str, Any], cam_name: str, date: str, fname: str) -> str:
    """Build the SMB destination path for one finalized segment.

    Layout: ``\\\\{server}\\{share}\\{smb_base_path}\\{nvr_smb_subpath}\\{cam}\\{date}\\{fname}``.
    Pure helper — no I/O. Called from the drain watcher per file.
    """
    server = (opts.get("smb_server") or "").strip()
    share = (opts.get("smb_share") or "").strip()
    base = (opts.get("smb_base_path") or "Bosch-Kameras").strip()
    sub = (opts.get("nvr_smb_subpath") or "NVR").strip()
    cam = _safe_name(cam_name)
    return f"\\\\{server}\\{share}\\{base}\\{sub}\\{cam}\\{date}\\{fname}".replace(
        "/", "\\"
    )


def _remote_ftp_path(opts: dict[str, Any], cam_name: str, date: str, fname: str) -> str:
    """Build the FTP destination path for one finalized segment.

    Layout: ``/{smb_base_path}/{nvr_smb_subpath}/{cam}/{date}/{fname}`` — FTP
    has no shares, paths are relative to the FTP login root.
    """
    base = (opts.get("smb_base_path") or "Bosch-Kameras").strip().strip("/")
    sub = (opts.get("nvr_smb_subpath") or "NVR").strip().strip("/")
    cam = _safe_name(cam_name)
    return f"/{base}/{sub}/{cam}/{date}/{fname}".replace("//", "/")


def _apply_quality(rtsp_url: str, quality: str) -> str:
    """Return a copy of rtsp_url with inst= adjusted for the requested quality.

    "low"  → inst=4 (~1.9 Mbps, LOCAL only — REMOTE rejects inst=4)
    "auto" → inst=1 (~30 Mbps, unchanged)
    If the URL has no inst= parameter and quality is "low", append &inst=4.
    Pure function so tests can exercise it without spawning ffmpeg.
    """
    if quality != "low":
        return rtsp_url
    if "inst=" in rtsp_url:
        return re.sub(r"inst=\d+", "inst=4", rtsp_url)
    # No inst= in URL — append it
    sep = "&" if "?" in rtsp_url else "?"
    return rtsp_url + sep + "inst=4"


def _build_ffmpeg_args(
    rtsp_url: str,
    segment_pattern: str,
    *,
    segment_seconds: int = DEFAULT_SEGMENT_SECONDS,
    quality: str = "auto",
) -> list[str]:
    """Return the exact ffmpeg argv used to record the stream.

    Pure function so tests can pin the wire format without spawning ffmpeg.
    Pattern is fed to ``-f segment`` via ``-strftime 1`` — ffmpeg substitutes
    ``%Y/%m/%d/%H/%M`` from the wall clock and creates parent directories
    implicitly via ``-segment_format mp4`` + ``-strftime_mkdir 1``.
    Phase 3: pass quality="low" to select inst=4 (~1.9 Mbps) instead of inst=1.
    """
    effective_url = _apply_quality(rtsp_url, quality)
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "warning",
        # Force TCP — RTP-over-UDP through the loopback proxy is fragile and
        # the TLS proxy already rewrites SETUP to TCP-interleaved anyway.
        "-rtsp_transport",
        "tcp",
        # -reconnect_* are HTTP-only options and crash ffmpeg with rc=8 on
        # rtsp:// inputs. The watcher (_watch_recorder) handles respawn on
        # TLS-proxy renewal gaps instead.
        "-i",
        effective_url,
        "-map",
        "0",  # include all streams (video + AAC audio) — MVP keeps audio per concept §10
        "-c",
        "copy",
        "-f",
        "segment",
        "-segment_time",
        str(segment_seconds),
        "-segment_format",
        "mp4",
        "-segment_atclocktime",
        "1",
        "-reset_timestamps",
        "1",
        "-strftime",
        "1",
        "-strftime_mkdir",
        "1",
        "-movflags",
        "+faststart",
        segment_pattern,
    ]


# ── Phase 4: pre-roll helpers ─────────────────────────────────────────────────


def _preroll_dir(cache_dir: str, cam_name: str) -> str:
    """Return {cache_dir}/{safe_cam_name}/"""
    return os.path.join(cache_dir, _safe_name(cam_name))


def _preroll_cam_dir(coordinator: BoschCameraCoordinator, cam_id: str) -> str:
    """Resolve one camera's pre-roll cache dir from coordinator options/data.

    Shared by every pre-roll reader/writer (`list_preroll_files`,
    `start_preroll_recorder`, `stop_preroll_recorder`,
    `finalize_and_restart_preroll_recorder`) so the cache_dir/cam_name
    resolution logic lives in exactly one place.
    """
    opts = coordinator.options
    cache_dir = (
        (
            opts.get("nvr_preroll_cache_dir")
            or "/dev/shm/bosch_nvr_cache"  # tmpfs NVR cache default, user-overridable via options
        ).strip()
    )
    cam_name = coordinator.data.get(cam_id, {}).get("info", {}).get("title", cam_id)
    return _preroll_dir(cache_dir, cam_name)


def _preroll_pattern(cache_dir: str, cam_name: str) -> str:
    """Strftime pattern for pre-roll 10 s segments in tmpfs."""
    return os.path.join(_preroll_dir(cache_dir, cam_name), "%H%M%S.mp4")


def _newest_preroll_path(cam_dir: str) -> str | None:
    """Return the currently-newest pre-roll segment path, or None if empty.

    Runs inside an executor job (filesystem I/O). Used by
    `finalize_and_restart_preroll_recorder` to identify the ring's actively-
    written segment *before* stopping it, so the now-finalized file can be
    handed back to the caller once the stop confirms a clean ffmpeg exit.
    """
    segs = _list_preroll_segments(cam_dir)
    return segs[-1][0] if segs else None


def _list_preroll_segments(cam_dir: str) -> list[tuple[str, float]]:
    """Return [(path, mtime)] sorted oldest-first for one camera's cache dir."""
    out: list[tuple[str, float]] = []
    if not os.path.isdir(cam_dir):
        return out
    try:
        names = os.listdir(cam_dir)
    except OSError:
        return out
    for name in names:
        full = os.path.join(cam_dir, name)
        if not os.path.isfile(full):
            continue
        try:
            st = os.stat(full)
        except OSError:
            continue
        if st.st_size < _PREROLL_MIN_SIZE_BYTES:
            continue
        out.append((full, st.st_mtime))
    out.sort(key=lambda x: x[1])
    return out


def prune_preroll_cache(cam_dir: str, max_segments: int) -> int:
    """Delete oldest segments keeping max_segments newest. Returns count deleted."""
    segs = _list_preroll_segments(cam_dir)
    to_delete = segs[: max(0, len(segs) - max_segments)]
    deleted = 0
    for path, _ in to_delete:
        try:
            os.unlink(path)
            deleted += 1
        except OSError:
            pass
    return deleted


def _prune_and_count(cam_dir: str, max_segments: int) -> int:
    """Prune then return remaining segment count. Runs inside executor job."""
    prune_preroll_cache(cam_dir, max_segments)
    return len(_list_preroll_segments(cam_dir))


def _build_preroll_ffmpeg_args(rtsp_url: str, pattern: str) -> list[str]:
    """Ffmpeg args for 10 s segments to tmpfs. No -segment_atclocktime, no -strftime_mkdir.
    No -reconnect* — those are HTTP-only and crash ffmpeg rc=8 on rtsp:// inputs.
    """
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "warning",
        "-rtsp_transport",
        "tcp",
        "-i",
        rtsp_url,
        "-map",
        "0",
        "-c",
        "copy",
        "-f",
        "segment",
        "-segment_time",
        str(_PREROLL_SEGMENT_SECONDS),
        "-segment_format",
        "mp4",
        "-reset_timestamps",
        "1",
        "-strftime",
        "1",
        "-movflags",
        "+faststart",
        pattern,
    ]


async def _watch_preroll_recorder(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    cam_dir: str,
    max_segs: int,
) -> None:
    """Periodic prune loop — keeps the pre-roll ring buffer bounded while running.

    Fires every _PREROLL_SEGMENT_SECONDS (10 s) and discards the oldest
    segments so the buffer never grows past max_segs × 10 s. Exits cleanly
    when the process exits or is cancelled.
    """
    while True:
        try:
            await asyncio.sleep(_PREROLL_SEGMENT_SECONDS)
        except asyncio.CancelledError:
            raise
        proc = coordinator.nvr_preroll_processes.get(cam_id)
        if proc is None or proc.returncode is not None:
            return
        try:
            remaining = await coordinator.hass.async_add_executor_job(
                _prune_and_count,
                cam_dir,
                max_segs,
            )
            coordinator.nvr_preroll_segment_counts[cam_id] = remaining
        except Exception:  # best-effort prune-on-stop; non-fatal if cache dir missing  # best-effort cache prune, non-fatal if dir missing
            pass


async def _spawn_preroll_recorder_locked(
    coordinator: BoschCameraCoordinator, cam_id: str
) -> None:
    """Spawn the pre-roll ffmpeg ring writer for one camera to tmpfs.

    Callers MUST already hold ``coordinator.get_nvr_recorder_lock(cam_id)``
    — factored out of `start_preroll_recorder` so
    `finalize_and_restart_preroll_recorder` can respawn the ring without
    releasing the lock between its own stop and this spawn (would reopen
    the exact race issue #44 fixed).
    """
    if getattr(coordinator, "nvr_shutting_down", False):
        # Config-entry unload/HA-stop is tearing this coordinator down
        # (issue #47) — refuse to spawn a new ring writer that
        # stop_all_preroll()'s sweep, running concurrently, might not see.
        _LOGGER.debug(
            "NVR pre-roll spawn skipped for %s — coordinator shutting down",
            cam_id[:8],
        )
        return
    live = coordinator.live_connections.get(cam_id, {})
    if live.get("_connection_type") != "LOCAL":
        return
    rtsp_url = live.get("rtspsUrl") or live.get("rtspUrl") or ""
    if not rtsp_url.startswith("rtsp://"):
        return

    opts = coordinator.options
    cache_dir = (
        (
            opts.get("nvr_preroll_cache_dir")
            or "/dev/shm/bosch_nvr_cache"  # tmpfs NVR cache default, user-overridable via options
        ).strip()
    )
    cam_name = coordinator.data.get(cam_id, {}).get("info", {}).get("title", cam_id)
    cam_dir = _preroll_dir(cache_dir, cam_name)
    try:
        await coordinator.hass.async_add_executor_job(
            os.makedirs,
            cam_dir,
            0o755,
            True,
        )
    except OSError as err:
        _LOGGER.warning(
            "NVR pre-roll: cannot create cache dir for %s: %s", cam_name, err
        )
        return

    pattern = _preroll_pattern(cache_dir, cam_name)
    args = _build_preroll_ffmpeg_args(rtsp_url, pattern)
    _LOGGER.debug("NVR pre-roll starting for %s -> %s", cam_name, pattern)
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        _LOGGER.error("NVR pre-roll: ffmpeg not found on PATH")
        return
    except OSError as err:
        _LOGGER.warning("NVR pre-roll ffmpeg spawn failed for %s: %s", cam_name, err)
        return

    coordinator.nvr_preroll_processes[cam_id] = proc
    # Compute max_segs once; used for prune-on-spawn and periodic watcher.
    preroll_secs = int(opts.get("nvr_preroll_seconds", 0))
    max_segs = max(2, math.ceil(preroll_secs / _PREROLL_SEGMENT_SECONDS) + 1)
    # Prune on spawn so stale segments from a previous session don't inflate the buffer.
    try:
        remaining = await coordinator.hass.async_add_executor_job(
            _prune_and_count,
            cam_dir,
            max_segs,
        )
        coordinator.nvr_preroll_segment_counts[cam_id] = remaining
    except Exception:  # best-effort prune-on-spawn; non-fatal if cache dir missing  # best-effort cache prune, non-fatal if dir missing
        pass

    # Start periodic prune watcher — keeps the ring buffer bounded while running.
    if not hasattr(coordinator, "nvr_preroll_tasks"):
        coordinator.nvr_preroll_tasks = {}
    task = coordinator.hass.async_create_background_task(
        _watch_preroll_recorder(coordinator, cam_id, cam_dir, max_segs),
        f"bosch_nvr_preroll_watch_{cam_id[:8]}",
    )
    coordinator.bg_tasks.add(task)
    task.add_done_callback(coordinator.bg_tasks.discard)
    coordinator.nvr_preroll_tasks[cam_id] = task


async def start_preroll_recorder(
    coordinator: BoschCameraCoordinator, cam_id: str
) -> None:
    """Spawn parallel pre-roll ffmpeg for one camera to tmpfs.

    Serialized on the same per-camera lock the main recorder spawn uses
    (issue #44, realKim-dotcom): this function was previously unserialized,
    unlike `start_recorder`'s spawn — two concurrent callers (switch
    turn-on, the stream-up hook, and the NVR mode select can all reach this
    for the same camera) could each pass the leading stop-then-spawn
    sequence, and the loser's process handle got overwritten in
    `_nvr_preroll_processes`, leaking an untracked second ffmpeg ring
    writer that interleaves segments with the first. `start_recorder`
    releases this lock before calling here, so holding it for this whole
    function cannot deadlock.
    """
    async with coordinator.get_nvr_recorder_lock(cam_id):
        # This is a respawn (fresh creds / restart), not a genuine stop —
        # keep the accumulated ring buffer instead of wiping it (see
        # prune_cache docstring on stop_preroll_recorder).
        await stop_preroll_recorder(coordinator, cam_id, prune_cache=False)
        await _spawn_preroll_recorder_locked(coordinator, cam_id)


async def stop_preroll_recorder(
    coordinator: BoschCameraCoordinator, cam_id: str, *, prune_cache: bool = True
) -> bool:
    """Stop pre-roll recorder for one camera and clear its tmpfs ring cache.

    Leftover segments from the just-stopped ring buffer are unlinked so they
    don't sit in ``/dev/shm`` until the next ``start_preroll_recorder()``
    happens to overwrite them (issue #43 follow-up, realKim-dotcom).

    ``prune_cache=False`` is used by ``start_preroll_recorder``'s own leading
    self-call (a respawn, e.g. LOCAL session/cred-rotation renewal) so the
    ring buffer keeps its accumulated context across a restart instead of
    being wiped to empty every renewal — a bug-hunt finding from the same
    issue #43 follow-up: an unconditional wipe here fired on every renewal
    (via ``start_recorder``'s own leading ``stop_recorder`` call), not just
    genuine stops, defeating the pre-roll buffer's purpose.

    Returns True iff a running process exited on SIGTERM within the grace
    window (i.e. ffmpeg finalized its own output cleanly, moov atom
    included). Returns False if there was nothing to stop, the process was
    already dead, or it had to be force-killed — `hard-kill` gives no
    guarantee the last-open segment file has a valid moov atom, so callers
    (`finalize_and_restart_preroll_recorder`) must treat False as "don't
    trust the newest segment file".
    """
    # Cancel the periodic prune watcher first.
    tasks = getattr(coordinator, "nvr_preroll_tasks", {})
    watcher = tasks.pop(cam_id, None)
    if watcher is not None and not watcher.done():
        watcher.cancel()

    coordinator.nvr_preroll_segment_counts.pop(cam_id, None)
    proc = coordinator.nvr_preroll_processes.pop(cam_id, None)
    clean_exit = False
    if proc is not None and proc.returncode is None:
        try:
            proc.send_signal(signal.SIGTERM)
        except ProcessLookupError:
            proc = None
        else:
            try:
                await asyncio.wait_for(proc.wait(), timeout=_STOP_GRACE_SECONDS)
                clean_exit = True
            except TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                try:
                    await asyncio.wait_for(
                        proc.wait(), timeout=TIMEOUT_RECORDER_KILL_WAIT
                    )
                except TimeoutError:
                    pass

    if not prune_cache:
        return clean_exit

    cam_dir = _preroll_cam_dir(coordinator, cam_id)
    try:
        await coordinator.hass.async_add_executor_job(prune_preroll_cache, cam_dir, 0)
    except Exception:  # best-effort cleanup; non-fatal if cache dir missing  # best-effort ring cleanup on stop, non-fatal if dir missing
        pass
    return clean_exit


def _known_cam_ids_for_shutdown(coordinator: BoschCameraCoordinator) -> set[str]:
    """All camera IDs that could plausibly have (or soon get) an NVR/ring
    ffmpeg process — used by the unload-time sweeps below.

    A plain ``list(coordinator.nvr_processes.keys())`` snapshot (the
    previous implementation) misses a camera whose ``start_recorder``/
    ``_spawn_preroll_recorder_locked`` call is still in flight and hasn't
    registered its process yet at snapshot time — issue #47's orphaned-
    ffmpeg finding. Including every currently-configured camera (not just
    ones with an already-tracked process) means the per-cam
    ``_get_nvr_recorder_lock`` acquire in ``stop_all``/``stop_all_preroll``
    below will still serialize against — and thus catch — that in-flight
    spawn once it finishes registering.
    """
    cam_ids = set(coordinator.nvr_processes) | set(coordinator.nvr_preroll_processes)
    cam_ids |= set(getattr(coordinator, "camera_entities", {}) or {})
    return cam_ids


async def stop_all_preroll(coordinator: BoschCameraCoordinator) -> None:
    """Stop all pre-roll recorders — called on integration unload.

    Serializes each camera on `_get_nvr_recorder_lock` (issue #47) so a
    `start_preroll_recorder`/`_spawn_preroll_recorder_locked` call that is
    still in flight when unload begins cannot race this sweep: it either
    hasn't acquired the lock yet (and will observe `_nvr_shutting_down` and
    bail once it does), or already holds the lock and finishes registering
    into `_nvr_preroll_processes` before this loop's own acquire for that
    camera unblocks and sees the freshly-spawned process.
    """
    for cam_id in _known_cam_ids_for_shutdown(coordinator):
        async with coordinator.get_nvr_recorder_lock(cam_id):
            await stop_preroll_recorder(coordinator, cam_id)


async def finalize_and_restart_preroll_recorder(
    coordinator: BoschCameraCoordinator, cam_id: str
) -> str | None:
    """Stop-finalize the ring's actively-written segment, then restart it.

    `list_preroll_files()` always drops the newest ring segment because it
    may still be mid-write with no moov atom — safe, but it can cost the
    freshest ~0-10 s of pre-roll footage, exactly the moment closest to an
    FCM event's trigger (feature request from realKim-dotcom's fork on
    issue #43, which SIGTERMs the ring, re-attaches the now-complete
    segment, then restarts). Gated behind the ``nvr_finalize_ring_on_event``
    option since it costs a real, if small (~1 s), gap in ring coverage on
    every event — opt-in, not a change to the default drop-newest behavior.

    Runs under the same per-camera lock `start_preroll_recorder`/
    `stop_preroll_recorder` use, held for the whole stop+respawn so no
    other caller can race in between (same discipline as issue #44's fix).
    If the ring writer isn't running (never started, or already crashed)
    there's nothing to finalize — this function does not itself resurrect
    it; that's `start_preroll_recorder`'s job (triggered elsewhere, e.g. by
    a LOCAL session renewal).

    The finalized segment is moved OUT of the pre-roll ring's own cache
    directory into a dedicated sibling dir, for two reasons: (1) so the
    freshly-respawned ring writer can never collide on the same
    strftime-derived filename if it happens to restart within the same
    wall-clock second, and (2) so `list_preroll_files()`'s own directory
    scan (run moments later by `create_motion_clip`) cannot pick this same
    file back up as an ordinary ring segment once newer segments make it
    no longer "the newest" — which would concatenate it into the clip
    TWICE (same class of bug already fixed once for the post-roll capture
    temp file, see the comment on `assemble_and_ship_motion_clip`).

    Returns the finalized segment's path if the ring had an active writer
    AND it exited cleanly on SIGTERM (moov atom guaranteed written) — the
    ring is always restarted in that case. Returns None if there was
    nothing to finalize (ring not running) or the stop had to hard-kill (no
    moov-atom guarantee, so the segment is discarded rather than trusted) —
    callers should silently fall back to the existing drop-newest behavior.
    """
    async with coordinator.get_nvr_recorder_lock(cam_id):
        proc = coordinator.nvr_preroll_processes.get(cam_id)
        if proc is None or proc.returncode is not None:
            return None
        cam_dir = _preroll_cam_dir(coordinator, cam_id)
        newest = await coordinator.hass.async_add_executor_job(
            _newest_preroll_path, cam_dir
        )
        if newest is None:
            return None
        clean_exit = await stop_preroll_recorder(coordinator, cam_id, prune_cache=False)

        opts = coordinator.options
        cache_dir = (
            (
                opts.get("nvr_preroll_cache_dir")
                or "/dev/shm/bosch_nvr_cache"  # tmpfs NVR cache default, user-overridable via options
            ).strip()
        )
        cam_name = coordinator.data.get(cam_id, {}).get("info", {}).get("title", cam_id)
        finalized_dir = os.path.join(cache_dir, "_finalized_tmp", _safe_name(cam_name))
        finalized_path = os.path.join(finalized_dir, os.path.basename(newest))

        def _relocate() -> str | None:
            try:
                os.makedirs(finalized_dir, mode=0o755, exist_ok=True)
                os.replace(newest, finalized_path)
            except OSError as err:
                _LOGGER.warning(
                    "NVR pre-roll finalize: cannot relocate finalized segment for %s: %s",
                    cam_name,
                    err,
                )
                return None
            return finalized_path

        relocated: str | None = await coordinator.hass.async_add_executor_job(_relocate)

        await _spawn_preroll_recorder_locked(coordinator, cam_id)

        if not clean_exit or relocated is None:
            # Hard-killed (no moov-atom guarantee) or the relocate failed —
            # don't hand back an untrustworthy/nonexistent path. If it was
            # relocated but is unusable, clean it up rather than leaking it
            # in the tmpfs cache forever.
            if relocated is not None:
                try:
                    await coordinator.hass.async_add_executor_job(os.unlink, relocated)
                except OSError:
                    pass
            return None
        return relocated


def list_preroll_files(coordinator: BoschCameraCoordinator, cam_id: str) -> list[str]:
    """Return list of pre-roll segment paths for cam_id, sorted oldest-first,
    safe to hand to `create_motion_clip`'s concat demuxer.

    The ring writer's ffmpeg `-f segment` process keeps exactly one file
    open at a time — the newest file on disk may still be mid-write with no
    finalized moov atom yet (it reaches the size threshold almost
    immediately after rotation, well before the 10 s segment period ends).
    Concatenating it produces a corrupt/failing clip. The ring is only ever
    consumed via this function (issue #43 follow-up bug report from
    realKim-dotcom: their own local event→clip patch hit exactly this and
    had to stop the ring writer first) — always drop the newest entry here
    rather than risk shipping a broken assembled clip. Costs at most one
    ~10 s segment of the freshest pre-roll footage (see
    `finalize_and_restart_preroll_recorder` for an opt-in way to recover
    that segment instead of dropping it).
    """
    cam_dir = _preroll_cam_dir(coordinator, cam_id)
    paths = [path for path, _ in _list_preroll_segments(cam_dir)]
    return paths[:-1] if paths else paths


def create_motion_clip_args(preroll_paths: list[str], output_path: str) -> list[str]:
    """Return ffmpeg argv to concat preroll_paths into one MP4 clip."""
    # Build concat list in memory via pipe — use -f concat -safe 0
    # The actual concat file is written by create_motion_clip before calling ffmpeg.
    concat_file = output_path + ".concat.txt"
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "warning",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_file,
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        "-y",
        output_path,
    ]


async def create_motion_clip(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    output_path: str,
    *,
    extra_segments: list[str] | None = None,
) -> bool:
    """Concatenate available pre-roll segments into output_path.

    ``extra_segments`` (optional) are appended, in order, after the pre-roll
    segments — used for the post-roll capture file (issue #43 follow-up) so
    a single clip covers both sides of the event without a second ffmpeg
    pass. Returns True on success.
    """
    paths = await coordinator.hass.async_add_executor_job(
        list_preroll_files,
        coordinator,
        cam_id,
    )
    if extra_segments:
        paths = [*paths, *extra_segments]
    if not paths:
        _LOGGER.debug("NVR motion clip: no pre-roll segments for %s", cam_id[:8])
        return False

    concat_file = output_path + ".concat.txt"
    concat_content = "\n".join(f"file '{p}'" for p in paths) + "\n"

    def _write_concat() -> None:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(concat_file, "w", encoding="utf-8") as f:
            f.write(concat_content)

    try:
        await coordinator.hass.async_add_executor_job(_write_concat)
    except OSError as err:
        _LOGGER.warning("NVR motion clip: cannot write concat file: %s", err)
        return False

    args = create_motion_clip_args(paths, output_path)
    _LOGGER.debug(
        "NVR motion clip for %s: %d segments -> %s", cam_id[:8], len(paths), output_path
    )
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        _LOGGER.error("NVR motion clip: ffmpeg not found on PATH")
        return False
    except OSError as err:
        _LOGGER.warning("NVR motion clip: ffmpeg spawn failed: %s", err)
        return False

    try:
        _, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=TIMEOUT_RECORDER_FFMPEG_INIT
        )
    except TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        _LOGGER.warning("NVR motion clip: ffmpeg timed out for %s", cam_id[:8])
        return False

    # Clean up concat file
    try:
        await coordinator.hass.async_add_executor_job(os.unlink, concat_file)
    except OSError:
        pass

    if proc.returncode != 0:
        tail = (stderr_bytes or b"").decode("utf-8", errors="replace").strip()[-300:]
        _LOGGER.warning(
            "NVR motion clip: ffmpeg rc=%d for %s. Tail: %s",
            proc.returncode,
            cam_id[:8],
            tail,
        )
        return False
    return True


# ── Phase 5: post-roll capture + event→clip assembly (issue #43) ────────────


def _build_postroll_capture_args(
    rtsp_url: str, output_path: str, duration_secs: int
) -> list[str]:
    """Ffmpeg argv for a single-shot fixed-duration live capture.

    Used to record the post-roll window right after an FCM motion event —
    ``-t`` makes ffmpeg exit on its own once the window has elapsed, no
    external signal needed. ``-c copy`` — no transcoding, matches every
    other recorder path in this module.
    """
    return [
        "ffmpeg",
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "warning",
        "-rtsp_transport",
        "tcp",
        "-i",
        rtsp_url,
        "-map",
        "0",
        "-c",
        "copy",
        "-t",
        str(duration_secs),
        "-movflags",
        "+faststart",
        "-y",
        output_path,
    ]


async def _capture_postroll(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    output_path: str,
    duration_secs: int,
) -> bool:
    """Record ``duration_secs`` of live LOCAL stream to ``output_path``.

    Returns True on success (rc=0 and file exists). Best-effort: any failure
    (camera not LOCAL, ffmpeg missing, timeout) just means the resulting clip
    falls back to pre-roll-only — never blocks or raises into the caller.
    """
    live = coordinator.live_connections.get(cam_id, {})
    if live.get("_connection_type") != "LOCAL":
        return False
    rtsp_url = live.get("rtspsUrl") or live.get("rtspUrl") or ""
    if not rtsp_url.startswith("rtsp://"):
        return False

    args = _build_postroll_capture_args(rtsp_url, output_path, duration_secs)
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError:
        _LOGGER.error("NVR post-roll capture: ffmpeg not found on PATH")
        return False
    except OSError as err:
        _LOGGER.warning("NVR post-roll capture: ffmpeg spawn failed: %s", err)
        return False

    try:
        _, stderr_bytes = await asyncio.wait_for(
            proc.communicate(),
            timeout=duration_secs + TIMEOUT_RECORDER_POSTROLL_GRACE,
        )
    except TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        _LOGGER.warning("NVR post-roll capture: ffmpeg timed out for %s", cam_id[:8])
        return False

    if proc.returncode != 0:
        tail = (stderr_bytes or b"").decode("utf-8", errors="replace").strip()[-300:]
        _LOGGER.warning(
            "NVR post-roll capture: ffmpeg rc=%d for %s. Tail: %s",
            proc.returncode,
            cam_id[:8],
            tail,
        )
        return False
    return True


async def assemble_and_ship_motion_clip(
    coordinator: BoschCameraCoordinator, cam_id: str
) -> bool:
    """On an FCM motion/person event, assemble a pre-roll(+post-roll) clip
    for a camera running in `event_buffered` Mini-NVR mode and drop it into
    the staging tree so the existing drain watcher promotes/uploads it like
    any continuous-mode segment.

    Guarded by a per-camera lock so overlapping FCM events don't race the
    concat-file write for the same camera; if an assembly is already in
    flight for this camera the new one is skipped rather than queued (a
    burst of events during one ongoing motion episode should not pile up
    redundant, mostly-overlapping clips). Returns True iff a clip was
    written to staging.

    No-ops (returns False without touching the ring buffer at all) if the
    per-camera ``nvr_event_clip`` switch has been turned off — an opt-out
    for installs that orchestrate their own clip-saving externally (e.g.
    via HA automations) and don't want a second, native clip produced on
    every event on top of their own (feature request, realKim-dotcom,
    issue #43 follow-up). The underlying pre-roll ring keeps running for
    such installs' own consumers; only this native assembly is skipped.
    """
    if not coordinator.get_nvr_event_clip_enabled(cam_id):
        _LOGGER.debug(
            "NVR motion clip: native event-clip assembly disabled for %s, skipping",
            cam_id[:8],
        )
        return False

    lock = coordinator.get_nvr_clip_assembly_lock(cam_id)
    if lock.locked():
        _LOGGER.debug(
            "NVR motion clip: assembly already in progress for %s, skipping",
            cam_id[:8],
        )
        return False

    async with lock:
        opts = coordinator.options
        base_path = (opts.get("nvr_base_path") or DEFAULT_BASE_PATH).strip()
        cam_name = coordinator.data.get(cam_id, {}).get("info", {}).get("title", cam_id)
        now = datetime.datetime.now(UTC)
        date_str = now.strftime("%Y-%m-%d")
        # Microsecond precision (not just HH-MM-SS): two motion events for
        # the same camera within the same wall-clock second would otherwise
        # collide on the output filename and the second ffmpeg -y silently
        # overwrites the first clip (bug-hunt finding, issue #43 follow-up).
        fname = now.strftime("%H-%M-%S-%f") + "_motion.mp4"
        staging_cam = _staging_dir(base_path, cam_name)
        dest_dir = os.path.join(staging_cam, date_str)
        output_path = os.path.join(dest_dir, fname)

        extra_segments: list[str] = []
        # Opt-in recovery of the freshest ring segment (issue #43 follow-up,
        # realKim-dotcom): normally `list_preroll_files()` drops it because
        # it may still be mid-write. Finalizing it costs a small ring gap on
        # every event, so it's gated behind its own option rather than on by
        # default.
        finalized_attached = False
        if opts.get("nvr_finalize_ring_on_event", False):
            finalized = await finalize_and_restart_preroll_recorder(coordinator, cam_id)
            if finalized:
                extra_segments.append(finalized)
                finalized_attached = True

        postroll_secs = int(opts.get("nvr_postroll_seconds") or 0)
        # NOT `_preroll_dir()` — that directory is scanned wholesale by
        # `list_preroll_files`/`_list_preroll_segments` with no filename
        # filter. Writing the post-roll capture there made it get picked up
        # as an extra "pre-roll" segment and concatenated into the clip
        # TWICE (bug-hunt finding, issue #43 follow-up). A dedicated sibling
        # directory keeps it invisible to the ring scan.
        postroll_tmp: str | None = None
        postroll_attached = False
        if postroll_secs > 0:
            cache_dir = (
                (
                    opts.get("nvr_preroll_cache_dir")
                    or "/dev/shm/bosch_nvr_cache"  # tmpfs NVR cache default, user-overridable via options
                ).strip()
            )
            postroll_dir = os.path.join(
                cache_dir, "_postroll_tmp", _safe_name(cam_name)
            )
            postroll_tmp = os.path.join(postroll_dir, fname)
            try:
                await coordinator.hass.async_add_executor_job(
                    os.makedirs, postroll_dir, 0o755, True
                )
            except OSError as err:
                _LOGGER.warning(
                    "NVR motion clip: cannot create postroll temp dir for %s: %s",
                    cam_name,
                    err,
                )
                postroll_tmp = None
            postroll_attached = postroll_tmp is not None and await _capture_postroll(
                coordinator, cam_id, postroll_tmp, postroll_secs
            )
            if postroll_attached and postroll_tmp is not None:
                extra_segments.append(postroll_tmp)
            # else: capture failed — `postroll_tmp` is deliberately kept
            # (not cleared) so the `finally` block below still unlinks any
            # partial file ffmpeg wrote before failing (bug-hunt finding:
            # previously this branch discarded the path, leaking the file).

        try:
            try:
                await coordinator.hass.async_add_executor_job(
                    os.makedirs, dest_dir, 0o755, True
                )
            except OSError as err:
                _LOGGER.warning(
                    "NVR motion clip: cannot create staging dir for %s: %s",
                    cam_name,
                    err,
                )
                return False

            shipped = await create_motion_clip(
                coordinator, cam_id, output_path, extra_segments=extra_segments
            )
        finally:
            if postroll_tmp is not None:
                try:
                    await coordinator.hass.async_add_executor_job(
                        os.unlink, postroll_tmp
                    )
                except OSError:
                    pass

        if shipped:
            _LOGGER.info(
                "NVR motion clip assembled for %s -> %s (postroll=%ds, finalized_segment=%s)",
                cam_name,
                output_path,
                postroll_secs if postroll_attached else 0,
                finalized_attached,
            )
        return shipped


def should_record(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    *,
    switch_on: bool,
) -> bool:
    """LAN-only gate. Returns True iff all three conditions hold:

    1. ``switch_on`` — user has toggled the per-camera NVR switch ON.
    2. The live session is LOCAL (NOT cloud relay).
    3. The camera is reachable (last status == ONLINE).

    Pure helper so tests can hit every combination without HA running.
    """
    if not switch_on:
        return False
    live = coordinator.live_connections.get(cam_id, {})
    if live.get("_connection_type") != "LOCAL":
        return False
    if not coordinator.is_camera_online(cam_id):
        return False
    return True


# ── recorder lifecycle (per-camera ffmpeg child) ─────────────────────────────


async def start_recorder(
    coordinator: BoschCameraCoordinator, cam_id: str, *, is_auto_retry: bool = False
) -> None:
    """Spawn (or replace) the ffmpeg recorder for one camera.

    Idempotent: if a recorder is already running for ``cam_id`` it is stopped
    first so the new one picks up fresh creds (heartbeat-cred rotation hook).
    Caller is responsible for the LAN-only check (`should_record`).

    ``is_auto_retry`` must be True ONLY when `_watch_recorder`'s own
    auth-failure branch calls this to respawn after a 401. A successful
    ffmpeg *spawn* is not proof the credential is actually valid — the RTSP
    DESCRIBE that would reveal a genuinely broken credential still happens
    after this returns. Resetting ``_nvr_auth_retry_count`` on every spawn
    (as this used to do unconditionally) made the give-up cap in
    `_watch_recorder` unreachable for a persistent auth fault: each retry's
    respawn immediately zeroed the counter the retry loop had just
    incremented, so it could never exceed 1. Every OTHER caller (switch
    toggle, coordinator tick, the non-auth crash-respawn path) still resets
    it, since those are legitimate "give this a fresh budget" moments.
    """
    # Replace any pre-existing recorder (cred rotation, switch re-toggle).
    # This is a respawn, not a genuine stop — keep the pre-roll ring buffer
    # instead of wiping it (issue #43 follow-up bug-hunt finding).
    await stop_recorder(coordinator, cam_id, prune_preroll_cache=False)

    live = coordinator.live_connections.get(cam_id, {})
    if live.get("_connection_type") != "LOCAL":
        _LOGGER.debug(
            "NVR start skipped for %s — not LOCAL (gate should have caught this)",
            cam_id[:8],
        )
        return
    # Poll for the TLS-proxy URL: when the NVR switch is toggled on right
    # after the Live Stream switch, the RTSP DESCRIBE handshake (~3–10 s on
    # Gen2) may still be in flight and ``_live_connections[cam_id].rtspsUrl``
    # is still empty. The coordinator tick would eventually retry, but the
    # immediate UI toggle would record an unwarranted WARNING every tick
    # until the URL lands. Wait up to 12 s in 500 ms steps before giving up.
    rtsp_url = live.get("rtspsUrl") or live.get("rtspUrl") or ""
    if not rtsp_url.startswith("rtsp://"):
        for _ in range(_PROXY_URL_WAIT_STEPS):
            await asyncio.sleep(_PROXY_URL_WAIT_INTERVAL)
            live = coordinator.live_connections.get(cam_id, {})
            if live.get("_connection_type") != "LOCAL":
                return  # stream torn down while we were waiting
            rtsp_url = live.get("rtspsUrl") or live.get("rtspUrl") or ""
            if rtsp_url.startswith("rtsp://"):
                break
        if not rtsp_url.startswith("rtsp://"):
            _LOGGER.warning(
                "NVR start skipped for %s — TLS-proxy URL not ready after %d s "
                "(stream warm-up too slow); next coordinator tick will retry",
                cam_id[:8],
                int(_PROXY_URL_WAIT_STEPS * _PROXY_URL_WAIT_INTERVAL),
            )
            return

    opts = coordinator.options

    # Event-only mode: skip continuous recording, run only the pre-roll ring
    # buffer. Motion events can still create clips from cached segments.
    # Resolved per-camera (GitHub #43) with fallback to the global option —
    # lets a mixed fleet run continuous-while-armed on cameras where PIR
    # can't fire (e.g. shooting through glass) while others stay event-only.
    if coordinator.get_nvr_mode(cam_id) == "event_buffered":
        preroll_secs = int(opts.get("nvr_preroll_seconds") or 0)
        if preroll_secs > 0:
            await start_preroll_recorder(coordinator, cam_id)
            # Push an immediate entity update so `mini_nvr_state`'s
            # preroll_running/preroll_segments attributes reflect reality the
            # instant the ring spawns, instead of waiting for the next
            # coordinator tick (issue #43 follow-up, realKim-dotcom).
            coordinator.async_update_listeners()
        return

    base_path = (opts.get("nvr_base_path") or DEFAULT_BASE_PATH).strip()
    cam_name = coordinator.data.get(cam_id, {}).get("info", {}).get("title", cam_id)
    # ffmpeg ALWAYS writes to a staging tree first — defends against
    # partial-writes during segment rotation. The drain watcher promotes
    # finalized files to either the local layout or to SMB / FTP, depending
    # on `nvr_storage_target`.
    pattern = _staging_pattern(base_path, cam_name)

    # Pre-create the staging camera dir AND today's/tomorrow's date subdir.
    # -strftime_mkdir 1 is unreliable on some ffmpeg versions bundled with HA
    # (confirmed rc=254 "Failed to open segment" on HA 2026-05-08). We create
    # the next 2 days so a recording that starts just before midnight doesn't
    # fail when ffmpeg rolls over to a new date subdirectory.
    staging_cam = _staging_dir(base_path, cam_name)
    try:
        for day_offset in range(2):
            day = (
                datetime.date.today() + datetime.timedelta(days=day_offset)
            ).strftime("%Y-%m-%d")
            await coordinator.hass.async_add_executor_job(
                os.makedirs,
                os.path.join(staging_cam, day),
                0o755,
                True,
            )
    except OSError as err:
        _LOGGER.warning(
            "NVR cannot create staging dir for %s: %s",
            cam_name,
            err,
        )
        return

    quality = (opts.get("nvr_quality") or "auto").strip().lower()

    _LOGGER.info(
        "NVR starting recorder for %s -> %s (quality=%s)",
        cam_name,
        pattern,
        quality,
    )
    # Issue #42 follow-up: the makedirs step above awaits an executor job,
    # long enough for a Bosch heartbeat to rotate LOCAL creds out from under
    # the `rtsp_url` captured earlier — ffmpeg would then connect with an
    # already-invalid cred pair and 401 on its first DESCRIBE. Re-read the
    # live URL right before spawning (closing the window to a few
    # microseconds) and hold the same lock `_refresh_local_creds_from_heartbeat`
    # uses while mutating `_live_connections`, so the two can't interleave.
    async with coordinator.get_nvr_recorder_lock(cam_id):
        if getattr(coordinator, "nvr_shutting_down", False):
            # Config-entry unload/HA-stop started while we were creating
            # staging dirs (issue #47) — refuse to spawn a process that
            # stop_all()'s concurrent sweep, serialized on this same lock,
            # might already have passed for this camera.
            _LOGGER.debug(
                "NVR start skipped for %s — coordinator shutting down",
                cam_id[:8],
            )
            return
        live = coordinator.live_connections.get(cam_id, {})
        if live.get("_connection_type") != "LOCAL":
            return  # stream torn down while we were creating staging dirs
        fresh_rtsp_url = live.get("rtspsUrl") or live.get("rtspUrl") or rtsp_url
        args = _build_ffmpeg_args(fresh_rtsp_url, pattern, quality=quality)
        _LOGGER.debug("NVR ffmpeg argv for %s: %s", cam_name, " ".join(args))
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            _LOGGER.error(
                "NVR cannot start — ffmpeg binary not found on PATH. "
                "Install ffmpeg or disable the NVR option.",
            )
            return
        except OSError as err:
            _LOGGER.warning("NVR ffmpeg spawn failed for %s: %s", cam_name, err)
            return

        coordinator.nvr_processes[cam_id] = proc
        # A fresh spawn is underway — clear any stale give-up/error state from a
        # prior crash-loop so the sensor doesn't keep showing "error" forever
        # after a successful restart (issue #42).
        coordinator.nvr_error_state.pop(cam_id, None)
        # Do NOT reset the auth-retry counter when THIS spawn is itself an
        # auto-retry from the auth-failure branch below — a successful
        # subprocess *spawn* is not proof the credential is valid (the RTSP
        # DESCRIBE that would reveal a persistent auth fault happens after
        # this returns). Resetting here unconditionally made the give-up cap
        # unreachable for a genuinely broken credential: each retry's own
        # respawn zeroed the counter the retry loop had just incremented.
        if not is_auto_retry:
            coordinator.nvr_auth_retry_count.pop(cam_id, None)
    # Push an immediate entity update so `mini_nvr_state` (and anything else
    # reading these dicts) reflects "recording" the instant ffmpeg actually
    # spawns, instead of waiting for the next ~60s coordinator tick (issue
    # #42 follow-up — realKim-dotcom, 2026-07-10: sensor read "idle" up to
    # 20s after the process was already up).
    coordinator.async_update_listeners()
    # Watcher coroutine restarts ffmpeg once on transient crash and gives up
    # if it crashes again within _RESPAWN_WINDOW_SECONDS.
    task = coordinator.hass.async_create_background_task(
        _watch_recorder(coordinator, cam_id, proc),
        f"bosch_nvr_watch_{cam_id[:8]}",
    )
    coordinator.bg_tasks.add(task)
    task.add_done_callback(coordinator.bg_tasks.discard)

    # Start pre-roll buffer if configured (nvr_preroll_seconds > 0).
    preroll_secs = int(opts.get("nvr_preroll_seconds") or 0)
    if preroll_secs > 0:
        await start_preroll_recorder(coordinator, cam_id)


async def stop_recorder(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    *,
    prune_preroll_cache: bool = True,
) -> None:
    """Stop the recorder for one camera, giving ffmpeg up to 5 s to flush MP4.

    ``prune_preroll_cache=False`` passes through to ``stop_preroll_recorder``
    — used by ``start_recorder``'s own leading self-call (a respawn, not a
    genuine stop) so a LOCAL session/cred-rotation renewal doesn't wipe the
    pre-roll ring buffer every time (issue #43 follow-up bug-hunt finding).
    """
    await stop_preroll_recorder(coordinator, cam_id, prune_cache=prune_preroll_cache)
    proc = coordinator.nvr_processes.pop(cam_id, None)
    if proc is None:
        return
    # Push immediately — `_nvr_processes` (the sensor's source of truth) is
    # already popped above, so "recording" flips to "idle" right now
    # regardless of how long the graceful-stop/SIGKILL sequence below takes.
    # Issue #42 follow-up: previously the sensor kept reading "recording"
    # for up to 1-2 minutes after a stop, waiting for the next coordinator
    # tick to notice the (already correct) state.
    coordinator.async_update_listeners()
    if proc.returncode is not None:
        _LOGGER.debug(
            "NVR stop_recorder: ffmpeg already exited for %s (rc=%d)",
            cam_id[:8],
            proc.returncode,
        )
        return
    try:
        proc.send_signal(signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(proc.wait(), timeout=_STOP_GRACE_SECONDS)
        _LOGGER.debug(
            "NVR stop_recorder: ffmpeg cleanly exited for %s (rc=%d)",
            cam_id[:8],
            proc.returncode,
        )
    except TimeoutError:
        _LOGGER.warning(
            "NVR stop_recorder: ffmpeg did not exit within %.0fs for %s — escalating to SIGKILL",
            _STOP_GRACE_SECONDS,
            cam_id[:8],
        )
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=TIMEOUT_RECORDER_KILL_WAIT)
        except TimeoutError:
            _LOGGER.warning(
                "NVR stop_recorder: ffmpeg still alive after SIGKILL for %s",
                cam_id[:8],
            )


async def stop_all(coordinator: BoschCameraCoordinator) -> None:
    """Stop every recorder — called on integration unload / HA stop.

    See `stop_all_preroll`'s docstring (issue #47): sweeps every known
    camera (not just ones with an already-tracked process) under
    `_get_nvr_recorder_lock`, so an in-flight `start_recorder` call cannot
    leave an untracked, never-killed ffmpeg process behind.
    """
    await stop_all_preroll(coordinator)
    for cam_id in _known_cam_ids_for_shutdown(coordinator):
        async with coordinator.get_nvr_recorder_lock(cam_id):
            await stop_recorder(coordinator, cam_id)


async def _watch_recorder(
    coordinator: BoschCameraCoordinator,
    cam_id: str,
    proc: asyncio.subprocess.Process,
) -> None:
    """Watch one ffmpeg child, retry-once-then-give-up.

    HA already owns the LOCAL→REMOTE fallback decision; the recorder just
    follows it.  When ffmpeg exits with a non-zero rc and the LAN-only gate
    is still True we treat it as a transient failure (camera blip, TLS-proxy
    cred rotation, network glitch) and respawn after _RESPAWN_DELAY_SECONDS.
    A second crash inside _RESPAWN_WINDOW_SECONDS = give up; the user has to
    toggle the switch off+on to retry.
    """
    started_at = time.monotonic()
    rc = await proc.wait()
    # If somebody already removed the proc from _nvr_processes (clean stop /
    # replacement) we're done — nothing to respawn.
    if coordinator.nvr_processes.get(cam_id) is not proc:
        return
    coordinator.nvr_processes.pop(cam_id, None)
    # Push immediately — an unexpected ffmpeg exit is a real "recording"→
    # "idle" transition the instant it's detected, not something that should
    # wait for the next coordinator tick (issue #42 follow-up, same reasoning
    # as stop_recorder above).
    coordinator.async_update_listeners()

    # Drain stderr for the first crash to surface ffmpeg's reason.
    err_tail = ""
    if proc.stderr is not None:
        try:
            err_bytes = await asyncio.wait_for(
                proc.stderr.read(2048), timeout=TIMEOUT_RECORDER_STDERR_DRAIN
            )
            err_tail = err_bytes.decode("utf-8", errors="replace").strip()
        except (  # best-effort stderr drain before respawn, exit already logged
            TimeoutError,
            Exception,
        ):  # best-effort stderr drain before respawn; ffmpeg exit already logged
            pass

    elapsed = time.monotonic() - started_at
    _LOGGER.warning(
        "NVR ffmpeg exited rc=%s after %.0fs for %s. Tail: %s",
        rc,
        elapsed,
        cam_id[:8],
        err_tail[-500:] if err_tail else "(no stderr)",
    )

    # Quick re-check: only respawn if we still want to record.
    last = getattr(coordinator, "nvr_user_intent", {}).get(cam_id, False)
    if not should_record(coordinator, cam_id, switch_on=last):
        _LOGGER.info("NVR not respawning for %s — gate now closed", cam_id[:8])
        return

    # B13-4: Detect disk-full — ENOSPC causes ffmpeg rc=1 with a specific
    # stderr message.  Raise a persistent HA notification and skip respawn
    # (the drive is still full, retrying immediately loops forever).
    _ENOSPC_MARKERS = ("no space left", "enospc", "disk quota exceeded")
    err_lower = err_tail.lower()
    if any(marker in err_lower for marker in _ENOSPC_MARKERS):
        _LOGGER.error(
            "NVR ffmpeg exited due to disk-full for %s — not respawning. "
            "Free space under %s and toggle the switch off+on to retry.",
            cam_id[:8],
            (coordinator.options.get("nvr_base_path") or DEFAULT_BASE_PATH),
        )
        coordinator.nvr_error_state[cam_id] = "disk full"
        coordinator.async_update_listeners()
        try:
            hass = getattr(coordinator, "hass", None)
            if hass is not None:
                # Already in the async event loop (_watch_recorder is an async def),
                # so schedule the task directly — no call_soon_threadsafe needed.
                # The coroutine is created INSIDE async_create_task to avoid an
                # eager-create / never-awaited coroutine object if the outer except
                # fires before the task is scheduled.
                hass.async_create_task(
                    hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": "Bosch Mini-NVR — Disk full",
                            "message": (
                                f"Recording stopped for camera {cam_id[:8]}: "
                                "no space left on device. "
                                f"Free space under "
                                f"{coordinator.options.get('nvr_base_path') or DEFAULT_BASE_PATH} "
                                "and toggle the NVR switch off+on to resume."
                            ),
                            "notification_id": f"bosch_nvr_diskfull_{cam_id[:8]}",
                        },
                    )
                )
        except Exception:  # best-effort UI notification; error already logged
            pass
        return

    # Issue #42: a 401/Unauthorized ffmpeg exit means it raced a Bosch
    # credential rotation — a known-transient condition (the next heartbeat
    # tick, or this very respawn once it lands after the rotation settles,
    # will pick up fresh creds), not a persistent fault. Counting it toward
    # the give-up threshold let two back-to-back cred-rotation races
    # permanently kill the recorder — observed as a ~1h recording gap when
    # the NVR switch was toggled on shortly after a LOCAL session opened.
    # Keep retrying on the normal delay/backoff without touching the crash
    # counter or the give-up error state.
    _AUTH_MARKERS = ("401", "unauthorized")
    if any(marker in err_lower for marker in _AUTH_MARKERS):
        retries = coordinator.nvr_auth_retry_count.get(cam_id, 0) + 1
        coordinator.nvr_auth_retry_count[cam_id] = retries
        if retries > _MAX_CONSECUTIVE_AUTH_RETRIES:
            _LOGGER.error(
                "NVR ffmpeg rejected with auth failures %d times in a row for "
                "%s — this is no longer consistent with a transient "
                "cred-rotation race. Toggle the recording switch off+on to "
                "retry.",
                retries,
                cam_id[:8],
            )
            coordinator.nvr_error_state[cam_id] = (
                "repeated auth failures — not a rotation race"
            )
            coordinator.async_update_listeners()
            return
        _LOGGER.warning(
            "NVR ffmpeg hit an auth failure for %s (cred-rotation race, "
            "%d/%d consecutive) — retrying without counting toward the "
            "crash-window give-up limit",
            cam_id[:8],
            retries,
            _MAX_CONSECUTIVE_AUTH_RETRIES,
        )
        await asyncio.sleep(_RESPAWN_DELAY_SECONDS)
        if not should_record(coordinator, cam_id, switch_on=last):
            return
        await start_recorder(coordinator, cam_id, is_auto_retry=True)
        return

    # B13-2: Always record the crash timestamp (not only for short-lived
    # crashes).  This closes the hole where a camera that crashes every 45 s
    # (i.e. elapsed > _RESPAWN_WINDOW_SECONDS) is never counted and respawns
    # forever because _nvr_recent_crash is never written.
    # The *give-up* gate still requires two crashes within the window.
    now = time.monotonic()
    prev_crash = coordinator.nvr_recent_crash.get(cam_id, float("-inf"))
    if (now - prev_crash) < _RESPAWN_WINDOW_SECONDS:
        _LOGGER.error(
            "NVR ffmpeg crashed twice within %.0fs for %s — giving up. "
            "Toggle the recording switch off+on to retry.",
            _RESPAWN_WINDOW_SECONDS,
            cam_id[:8],
        )
        coordinator.nvr_error_state[cam_id] = "ffmpeg crashed twice"
        coordinator.async_update_listeners()
        return
    coordinator.nvr_recent_crash[cam_id] = now

    await asyncio.sleep(_RESPAWN_DELAY_SECONDS)
    if not should_record(coordinator, cam_id, switch_on=last):
        return
    _LOGGER.info("NVR respawning ffmpeg for %s after transient crash", cam_id[:8])
    await start_recorder(coordinator, cam_id)


# ── staging-drain watcher (per-coordinator background task) ──────────────────


def _list_staging_candidates(
    staging_root: str,
) -> list[tuple[str, str, str, float, int]]:
    """Walk the staging tree and return ``(full_path, cam, date, mtime, size)``
    tuples for every regular file. Pure helper so the watcher is testable
    without spinning up an event loop.
    """
    out: list[tuple[str, str, str, float, int]] = []
    if not os.path.isdir(staging_root):
        return out
    # Layout: {staging_root}/{cam}/{date}/{file}.mp4
    try:
        cams = os.listdir(staging_root)
    except OSError:
        return out
    for cam in cams:
        cam_dir = os.path.join(staging_root, cam)
        if not os.path.isdir(cam_dir):
            continue
        try:
            dates = os.listdir(cam_dir)
        except OSError:
            continue
        for date in dates:
            date_dir = os.path.join(cam_dir, date)
            if not os.path.isdir(date_dir):
                continue
            try:
                files = os.listdir(date_dir)
            except OSError:
                continue
            for fname in files:
                full = os.path.join(date_dir, fname)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                # Pin only regular files
                if not os.path.isfile(full):
                    continue
                out.append((full, cam, date, st.st_mtime, st.st_size))
    return out


def _is_segment_finalized(mtime: float, size: int, *, now: float | None = None) -> bool:
    """Return True iff the segment is old enough AND big enough to upload.

    Both thresholds together avoid uploading a half-written ffmpeg segment
    mid-rotation. Pure function for testability.
    """
    now_ts = now if now is not None else time.time()
    return (
        size >= _DRAIN_MIN_SIZE_BYTES
        and (now_ts - mtime) >= _DRAIN_FINALIZE_AGE_SECONDS
    )


def _move_local(
    coordinator: BoschCameraCoordinator,
    full: str,
    base_path: str,
    cam: str,
    date: str,
    fname: str,
) -> bool:
    """target=local: rename staging file into ``{base}/{cam}/{date}/{fname}``.

    Returns True on success. The promoted layout is what Media Source / the
    retention purge already understand. Synchronous — runs inside the
    executor job that wraps the watcher tick.
    """
    dest_dir = os.path.join(base_path, cam, date)
    dest = os.path.join(dest_dir, fname)
    try:
        os.makedirs(dest_dir, mode=0o755, exist_ok=True)
        # ``shutil.move`` falls back to copy+unlink across filesystems
        # (e.g. if the user mounted a NAS at the base path).
        shutil.move(full, dest)
        return True
    except OSError as err:
        _LOGGER.debug("NVR drain (local): move %s -> %s failed: %s", full, dest, err)
        return False


def _upload_smb(
    coordinator: BoschCameraCoordinator, full: str, cam: str, date: str, fname: str
) -> bool:
    """target=smb: upload one finalized segment via smbclient.

    Reuses the session-register pattern from ``smb.py`` but writes only to
    the NVR subtree (``{smb_base_path}/{nvr_smb_subpath}``) so cloud-event
    uploads stay in their own branch.
    """
    try:
        # smbclient is an optional third-party dependency — deferred so its
        # absence only disables SMB-target NVR drain, not the whole module.
        from smbclient import open_file, register_session  # noqa: PLC0415
    except ImportError:
        _LOGGER.warning(
            "NVR drain (smb): smbprotocol not installed — install or set "
            "nvr_storage_target=local"
        )
        return False
    opts = coordinator.options
    server = (opts.get("smb_server") or "").strip()
    username = (opts.get("smb_username") or "").strip()
    password = opts.get("smb_password") or ""
    if not server:
        _LOGGER.debug("NVR drain (smb): smb_server is empty — skip")
        return False
    try:
        register_session(server, username=username, password=password)
    except Exception as err:
        _LOGGER.warning("NVR drain (smb): session to %s failed: %s", server, err)
        return False

    # Build remote path + ensure the per-date folder exists.
    base = (opts.get("smb_base_path") or "Bosch-Kameras").strip()
    sub = (opts.get("nvr_smb_subpath") or "NVR").strip()
    server_share = f"\\\\{server}\\{(opts.get('smb_share') or '').strip()}"
    folder_parts = f"{sub}/{cam}/{date}"
    smb_folder = f"{server_share}\\{base}\\{folder_parts}".replace("/", "\\")
    try:
        smb_makedirs(
            smb_folder,
            server,
            (opts.get("smb_share") or "").strip(),
            base,
            folder_parts,
        )
    except Exception as err:
        _LOGGER.debug("NVR drain (smb): mkdir %s failed: %s", smb_folder, err)
        return False

    dest = _remote_smb_path(opts, cam, date, fname)
    try:
        with open(full, "rb") as src, open_file(dest, mode="wb") as dst:
            for chunk in iter(lambda: src.read(65536), b""):
                dst.write(chunk)
        return True
    except Exception as err:
        _LOGGER.warning("NVR drain (smb): upload %s -> %s failed: %s", full, dest, err)
        return False


def _upload_ftp(
    coordinator: BoschCameraCoordinator, full: str, cam: str, date: str, fname: str
) -> bool:
    """target=ftp: upload one finalized segment via ftplib."""
    opts = coordinator.options
    server = (opts.get("smb_server") or "").strip()
    username = (opts.get("smb_username") or "").strip()
    password = opts.get("smb_password") or ""
    if not server:
        _LOGGER.debug("NVR drain (ftp): smb_server is empty — skip")
        return False
    try:
        ftp = _ftp_connect(server, username, password)
    except Exception as err:
        _LOGGER.warning("NVR drain (ftp): login to %s failed: %s", server, err)
        return False
    try:
        base = (opts.get("smb_base_path") or "Bosch-Kameras").strip().strip("/")
        sub = (opts.get("nvr_smb_subpath") or "NVR").strip().strip("/")
        cam_safe = _safe_name(cam)
        ftp_dir = f"/{base}/{sub}/{cam_safe}/{date}".replace("//", "/").rstrip("/")
        try:
            _ftp_makedirs(ftp, ftp_dir)
        except Exception as err:
            _LOGGER.debug("NVR drain (ftp): mkdir %s failed: %s", ftp_dir, err)
            return False
        dest = f"{ftp_dir}/{fname}"
        try:
            with open(full, "rb") as src:
                ftp.storbinary(f"STOR {dest}", src)
            return True
        except Exception as err:
            _LOGGER.warning(
                "NVR drain (ftp): upload %s -> %s failed: %s", full, dest, err
            )
            return False
    finally:
        try:
            ftp.quit()
        except Exception:  # best-effort graceful FTP quit; fallback to close below
            try:
                ftp.close()
            except (  # best-effort FTP teardown, failure non-actionable
                Exception
            ):  # best-effort FTP socket close on teardown, failure non-actionable
                pass


def _quarantine_failed(
    base_path: str, full: str, cam: str, date: str, fname: str
) -> None:
    """Move a file that exceeded the retry cap into ``{base}/_failed/{cam}/...``.

    Keeps the user's recording around for inspection without endlessly
    spamming upload retries each tick.
    """
    dest_dir = os.path.join(_failed_dir(base_path, cam), date)
    try:
        os.makedirs(dest_dir, mode=0o755, exist_ok=True)
        shutil.move(full, os.path.join(dest_dir, fname))
    except OSError as err:
        _LOGGER.debug("NVR drain: quarantine of %s failed: %s", full, err)


def sync_drain_tick(
    coordinator: BoschCameraCoordinator, *, now: float | None = None
) -> dict[str, int]:
    """One synchronous drain pass over the staging tree.

    Pure-ish helper (touches disk + may do network I/O via the upload
    callbacks) — runs inside an executor job. Returns a counters dict the
    caller (the async watcher) can fold into the per-camera state used by
    ``BoschNvrStateSensor``.
    """
    opts = coordinator.options
    base_path = (opts.get("nvr_base_path") or DEFAULT_BASE_PATH).strip()
    target = (opts.get("nvr_storage_target") or "local").lower()
    staging_root = os.path.join(base_path, _STAGING_DIRNAME)

    # Per-camera retry counter survives across ticks via the coordinator.
    if not hasattr(coordinator, "nvr_drain_failures"):
        coordinator.nvr_drain_failures = {}
    failures: dict[str, int] = coordinator.nvr_drain_failures

    promoted = uploaded = failed = 0
    pending = 0
    last_age: dict[str, float] = {}
    now_ts = now if now is not None else time.time()

    candidates = _list_staging_candidates(staging_root)
    for full, cam, date, mtime, size in candidates:
        # Always update the age stat so the sensor shows "fresh segment seen
        # but waiting to finalize" even before a successful drain.
        last_age[cam] = now_ts - mtime
        if not _is_segment_finalized(mtime, size, now=now_ts):
            pending += 1
            continue

        ok = False
        if target == "local":
            ok = _move_local(
                coordinator, full, base_path, cam, date, os.path.basename(full)
            )
            if ok:
                promoted += 1
        elif target == "smb":
            ok = _upload_smb(coordinator, full, cam, date, os.path.basename(full))
            if ok:
                uploaded += 1
                try:
                    os.unlink(full)
                except OSError as err:
                    _LOGGER.debug(
                        "NVR drain: unlink %s after smb upload failed: %s", full, err
                    )
        elif target == "ftp":
            ok = _upload_ftp(coordinator, full, cam, date, os.path.basename(full))
            if ok:
                uploaded += 1
                try:
                    os.unlink(full)
                except OSError as err:
                    _LOGGER.debug(
                        "NVR drain: unlink %s after ftp upload failed: %s", full, err
                    )
        else:
            _LOGGER.debug("NVR drain: unknown target %r — treating as local", target)
            ok = _move_local(
                coordinator, full, base_path, cam, date, os.path.basename(full)
            )
            if ok:
                promoted += 1

        if ok:
            failures.pop(full, None)
            continue

        failed += 1
        failures[full] = failures.get(full, 0) + 1
        if failures[full] >= _DRAIN_MAX_RETRIES:
            _LOGGER.error(
                "NVR drain: %s exceeded %d retries — quarantining to _failed/",
                full,
                _DRAIN_MAX_RETRIES,
            )
            _quarantine_failed(base_path, full, cam, date, os.path.basename(full))
            failures.pop(full, None)
            # Best-effort persistent notification — surface to the user.
            try:
                hass = getattr(coordinator, "hass", None)
                if hass is not None:
                    # sync_drain_tick runs in an executor thread, so we need
                    # call_soon_threadsafe to schedule onto the event loop.
                    # The coroutine is created INSIDE the lambda so it is only
                    # constructed on the loop thread — never an eager-create /
                    # never-awaited object sitting on a foreign thread.
                    _msg = (
                        f"Failed to drain {os.path.basename(full)} "
                        f"after {_DRAIN_MAX_RETRIES} attempts. "
                        f"File moved to {_failed_dir(base_path, cam)}."
                    )
                    _nid = f"bosch_nvr_drain_failed_{cam}"
                    hass.loop.call_soon_threadsafe(
                        hass.async_create_task,
                        hass.services.async_call(
                            "persistent_notification",
                            "create",
                            {
                                "title": "Bosch Mini-NVR — Upload failed",
                                "message": _msg,
                                "notification_id": _nid,
                            },
                        ),
                    )
            except (  # best-effort UI notify; quarantine + error already logged
                Exception
            ):  # best-effort UI notification; quarantine + error log already done above
                pass

    # Persist the latest drain stats on the coordinator so the sensor can
    # render them. ``_nvr_drain_state`` is created on first tick.
    state: dict[str, Any] = getattr(coordinator, "nvr_drain_state", None) or {}
    state["target"] = target
    state["pending"] = pending
    state["promoted"] = promoted
    state["uploaded"] = uploaded
    state["failed"] = failed
    state["last_age_by_cam"] = last_age
    state["last_tick_ts"] = now_ts
    coordinator.nvr_drain_state = state

    return {
        "promoted": promoted,
        "uploaded": uploaded,
        "failed": failed,
        "pending": pending,
    }


async def drain_staging_to_remote(coordinator: BoschCameraCoordinator) -> None:
    """Long-running watcher coroutine — one per coordinator (NOT per camera).

    Drives ``sync_drain_tick`` on a 30 s schedule via the HA executor pool so
    the synchronous SMB / FTP I/O never blocks the event loop. Cancellation
    is the supported stop path; ``async_unload_entry`` arranges that.
    """
    while True:
        try:
            opts = coordinator.options
            if opts.get("enable_nvr", False):
                try:
                    await coordinator.hass.async_add_executor_job(
                        sync_drain_tick,
                        coordinator,
                    )
                except Exception as err:
                    _LOGGER.warning("NVR drain tick raised: %s", err)
            await asyncio.sleep(_DRAIN_TICK_SECONDS)
        except asyncio.CancelledError:
            _LOGGER.debug("NVR drain watcher cancelled — exiting")
            raise


# ── retention purge (runs in executor thread, once per day) ──────────────────


def sync_nvr_cleanup(coordinator: BoschCameraCoordinator) -> None:
    """Delete NVR segments older than ``nvr_retention_days``.

    Dispatches based on ``nvr_storage_target``:
      * ``local`` → walk the on-disk tree under ``nvr_base_path`` (mirrors
        ``sync_smb_cleanup``: os.walk + cutoff math).
      * ``smb``   → walk only the NVR subtree
        ``{smb_base_path}/{nvr_smb_subpath}`` via smbclient.scandir.
      * ``ftp``   → walk only ``/{smb_base_path}/{nvr_smb_subpath}`` via
        ftplib LIST + MDTM.

    Always also purges the local ``_staging`` and ``_failed`` trees because
    those live under ``nvr_base_path`` regardless of the target. Same daily
    schedule as ``sync_smb_cleanup`` (called from ``_run_nvr_cleanup_bg``).
    """
    opts = coordinator.options
    retention_days = int(opts.get("nvr_retention_days", DEFAULT_RETENTION_DAYS))
    if retention_days <= 0:
        return
    target = (opts.get("nvr_storage_target") or "local").lower()
    if target == "smb":
        _sync_nvr_cleanup_smb(coordinator)
    elif target == "ftp":
        _sync_nvr_cleanup_ftp(coordinator)
    _sync_nvr_cleanup_local(coordinator)


def _sync_nvr_cleanup_local(coordinator: BoschCameraCoordinator) -> None:
    """Local-disk retention purge — covers ``local`` target plus the staging /
    failed dirs (which exist no matter the target).
    """
    opts = coordinator.options
    base_path = (opts.get("nvr_base_path") or DEFAULT_BASE_PATH).strip()
    retention_days = int(opts.get("nvr_retention_days", DEFAULT_RETENTION_DAYS))
    if retention_days <= 0 or not base_path or not os.path.isdir(base_path):
        return

    cutoff = time.time() - retention_days * 86400
    deleted = 0
    for root, _dirs, files in os.walk(base_path):
        for name in files:
            full = os.path.join(root, name)
            try:
                st = os.stat(full)
            except OSError:
                continue
            if st.st_mtime < cutoff:
                try:
                    os.remove(full)
                    deleted += 1
                except OSError as err:
                    _LOGGER.debug("NVR cleanup: cannot remove %s: %s", full, err)
    # Second pass: prune empty date folders (but never the camera dir or
    # base_path itself).
    for root, _dirs, _files in os.walk(base_path, topdown=False):
        if root == base_path:
            continue
        try:
            if not os.listdir(root):
                os.rmdir(root)
        except OSError:
            pass
    if deleted:
        _LOGGER.info(
            "NVR cleanup (local): deleted %d file(s) older than %d days from %s",
            deleted,
            retention_days,
            base_path,
        )


def _sync_nvr_cleanup_smb(coordinator: BoschCameraCoordinator) -> None:
    """Walk only the NVR subtree on the SMB share and unlink old files."""
    try:
        # Optional dependency, see _drain_nvr_smb docstring — deferred so its
        # absence only disables this SMB-target cleanup path.
        from smbclient import (  # noqa: PLC0415
            register_session,
            remove,
            scandir,
            stat as smb_stat,
        )
    except ImportError:
        return
    opts = coordinator.options
    server = (opts.get("smb_server") or "").strip()
    share = (opts.get("smb_share") or "").strip()
    username = (opts.get("smb_username") or "").strip()
    password = opts.get("smb_password") or ""
    base_path = (opts.get("smb_base_path") or "Bosch-Kameras").strip()
    sub = (opts.get("nvr_smb_subpath") or "NVR").strip()
    retention_days = int(opts.get("nvr_retention_days", DEFAULT_RETENTION_DAYS))
    if not server or not share or retention_days <= 0:
        return
    try:
        register_session(server, username=username, password=password)
    except Exception as err:
        _LOGGER.warning("NVR cleanup (smb): session to %s failed: %s", server, err)
        return

    cutoff = time.time() - retention_days * 86400
    root = f"\\\\{server}\\{share}\\{base_path}\\{sub}"
    deleted = 0
    deadline = time.monotonic() + _NVR_CLEANUP_MAX_SECONDS
    deadline_hit = False

    def _walk_and_delete(path: str) -> None:
        nonlocal deleted, deadline_hit
        if time.monotonic() > deadline:
            deadline_hit = True
            return
        try:
            entries = list(scandir(path))
        except Exception:
            return
        for entry in entries:
            if time.monotonic() > deadline:
                deadline_hit = True
                return
            full = f"{path}\\{entry.name}"
            if entry.is_dir():
                _walk_and_delete(full)
            else:
                try:
                    st = smb_stat(full)
                    if st.st_mtime < cutoff:
                        remove(full)
                        deleted += 1
                except Exception as err:
                    _LOGGER.debug("NVR cleanup (smb): error on %s: %s", entry.name, err)

    _walk_and_delete(root)
    if deadline_hit:
        _LOGGER.warning(
            "NVR cleanup (smb): deadline (%.0fs) exceeded, walk stopped early — "
            "some old files under %s may remain until the next cleanup run",
            _NVR_CLEANUP_MAX_SECONDS,
            root,
        )
    if deleted:
        _LOGGER.info(
            "NVR cleanup (smb): deleted %d file(s) older than %d days from %s",
            deleted,
            retention_days,
            root,
        )


def _sync_nvr_cleanup_ftp(coordinator: BoschCameraCoordinator) -> None:
    """Walk only the NVR subtree on the FTP server and unlink old files."""
    opts = coordinator.options
    server = (opts.get("smb_server") or "").strip()
    username = (opts.get("smb_username") or "").strip()
    password = opts.get("smb_password") or ""
    base_path = (opts.get("smb_base_path") or "Bosch-Kameras").strip().strip("/")
    sub = (opts.get("nvr_smb_subpath") or "NVR").strip().strip("/")
    retention_days = int(opts.get("nvr_retention_days", DEFAULT_RETENTION_DAYS))
    if not server or retention_days <= 0:
        return
    try:
        ftp = _ftp_connect(server, username, password)
    except Exception as err:
        _LOGGER.warning("NVR cleanup (ftp): login to %s failed: %s", server, err)
        return

    cutoff = time.time() - retention_days * 86400
    deleted = 0
    deadline = time.monotonic() + _NVR_CLEANUP_MAX_SECONDS
    deadline_hit = False

    def _walk_and_delete(path: str) -> None:
        nonlocal deleted, deadline_hit
        if time.monotonic() > deadline:
            deadline_hit = True
            return
        try:
            ftp.cwd(path)
        except ftplib.error_perm:
            return
        entries: list[str] = []
        try:
            ftp.retrlines("LIST", entries.append)
        except Exception:
            return

        files: list[str] = []
        subdirs: list[str] = []
        for line in entries:
            parts = line.split(None, 8)
            if len(parts) < 9:
                continue
            perms, name = parts[0], parts[-1]
            if name in (".", ".."):
                continue
            if perms.startswith("d"):
                subdirs.append(name)
            elif perms.startswith("-"):
                files.append(name)

        for name in files:
            if time.monotonic() > deadline:
                deadline_hit = True
                return
            # B13-6: use absolute paths for MDTM and DELETE so the commands are
            # position-independent even if a recursive _walk_and_delete call
            # left the FTP working-directory pointing at a subdirectory.
            abs_name = f"{path}/{name}"
            try:
                resp = ftp.sendcmd(f"MDTM {abs_name}")
                ts_str = resp.split()[-1]
                mt = (
                    datetime.datetime.strptime(ts_str[:14], "%Y%m%d%H%M%S")
                    .replace(tzinfo=UTC)
                    .timestamp()
                )
            except Exception:  # skip file if MDTM unavailable; resilient FTP walk loop  # skip file if MDTM unavailable, resilient walk
                continue
            if mt < cutoff:
                try:
                    ftp.delete(abs_name)
                    deleted += 1
                except Exception as err:
                    _LOGGER.debug(
                        "NVR cleanup (ftp): delete %s failed: %s", abs_name, err
                    )
        for sd in subdirs:
            _walk_and_delete(f"{path}/{sd}")
            try:
                ftp.cwd(path)
            except (  # best-effort cwd restore, sibling loop continues
                Exception
            ):  # best-effort cwd back to parent after subdir walk; non-fatal
                pass

    try:
        root = f"/{base_path}/{sub}"
        _walk_and_delete(root)
    finally:
        try:
            ftp.quit()
        except (  # best-effort FTP teardown, failure non-actionable
            Exception
        ):  # best-effort FTP quit on cleanup teardown, failure non-actionable
            pass
    if deadline_hit:
        _LOGGER.warning(
            "NVR cleanup (ftp): deadline (%.0fs) exceeded, walk stopped early — "
            "some old files under %s may remain until the next cleanup run",
            _NVR_CLEANUP_MAX_SECONDS,
            f"{server}/{base_path}/{sub}",
        )
    if deleted:
        _LOGGER.info(
            "NVR cleanup (ftp): deleted %d file(s) older than %d days from %s",
            deleted,
            retention_days,
            f"{server}/{base_path}/{sub}",
        )

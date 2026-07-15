"""MJPEG inst=3 snapshot helper for Gen2 Bosch Smart Home Cameras.

Gen2 cameras (HOME_Eyes_Outdoor, HOME_Eyes_Indoor) expose an undocumented
MJPEG stream on RTSP inst=3 (RTP/AVP 26). This module provides a helper
that captures exactly one JPEG frame from that stream via an FFmpeg subprocess.

APPROACH: FFmpeg subprocess (not native RTSP)
  A pure-Python RTSP+RTP+MJPEG client requires >500 LOC (RTSP handshake,
  Digest auth, RTP fragmentation, JFIF reassembly). Using asyncio.subprocess
  with FFmpeg achieves the same result in ~20 LOC. FFmpeg is always available
  in HA (required by the stream component), so there is no extra dependency.
  Subprocess overhead reduces the latency advantage vs. snap.jpg, but the
  result is still faster than a cloud-proxy round-trip on a healthy LAN:
  ~150-300 ms vs. ~500-1500 ms via REMOTE snap.jpg.

Auth: Digest credentials from PUT /v11/video_inputs/{id}/connection LOCAL.
  The rotating ~60 s TTL means snapshots must use a recently-fetched cred pair.
"""

from __future__ import annotations

import asyncio
import logging
import time
from urllib.parse import quote

_LOGGER = logging.getLogger(__name__)

# Minimal sanity check: a valid JPEG starts with 0xFF 0xD8
_JPEG_MAGIC = b"\xff\xd8"

MJPEG_INST = 3  # RTSP stream instance for MJPEG on Gen2 cameras


async def fetch_mjpeg_snapshot(
    cam_host: str,
    cam_port: int,
    user: str,
    password: str,
    *,
    timeout: float = 8.0,
) -> bytes | None:
    """Capture one JPEG frame from the Gen2 MJPEG stream (inst=3).

    Connects to ``rtsps://{user}:{password}@{cam_host}:{cam_port}/rtsp_tunnel
    ?inst=3`` via an FFmpeg subprocess, extracts exactly one frame and returns
    it as JPEG bytes.

    Args:
        cam_host:  Camera LAN IP or hostname (e.g. "192.0.2.149")
        cam_port:  Camera RTSP-over-TLS port (always 443 for Bosch cameras)
        user:      CBS username from PUT /connection (e.g. "cbs-XXXXXXXX")
        password:  Digest password from PUT /connection
        timeout:   Maximum seconds to wait for a frame. Default 8 s matches
                   TIMEOUT_SNAP in const.py.

    Returns:
        JPEG bytes on success; None on timeout, subprocess error, or empty
        output.
    """
    if not cam_host or not user or not password:
        _LOGGER.debug("fetch_mjpeg_snapshot: missing required params — skipping")
        return None

    # URL-encode user + password — Bosch cbs Digest passwords contain
    # special chars (`@`, `:`, `/`, `{`, `|`, etc.) that break URI parsing
    # if interpolated raw. Without quoting FFmpeg reports "Port missing in uri".
    safe_user = quote(user, safe="")
    safe_pass = quote(password, safe="")
    # Bosch cameras serve RTSPS on port 443 (TLS-wrapped). FFmpeg's `rtsp://`
    # over plain TCP fails with "Invalid data found when processing input" —
    # the bytes received are TLS records, not RTSP. Use `rtsps://` which
    # tells FFmpeg to negotiate TLS first.
    rtsp_url = (
        f"rtsps://{safe_user}:{safe_pass}@{cam_host}:{cam_port}"
        f"/rtsp_tunnel?inst={MJPEG_INST}"
    )

    t0 = time.monotonic()
    proc: asyncio.subprocess.Process | None = None
    try:
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg",
            # Silence all info/warning output — we only care about stdout
            "-loglevel",
            "error",
            # TLS: camera uses a Bosch private CA — skip verification
            "-rtsp_flags",
            "prefer_tcp",
            "-allowed_media_types",
            "video",
            "-i",
            rtsp_url,
            # Exactly one video frame
            "-vframes",
            "1",
            # MJPEG → JPEG passthrough (no re-encode, ~0 CPU)
            "-c:v",
            "copy",
            # Output as raw JPEG bytes to stdout
            "-f",
            "image2pipe",
            "-",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        elapsed_ms = (time.monotonic() - t0) * 1000

        rc = proc.returncode
        if rc != 0:
            err_text = err.decode(errors="replace")[:200] if err else "(no stderr)"
            # A negative return code means FFmpeg was killed by a signal
            # (e.g. -9 SIGKILL / -15 SIGTERM). That is the normal teardown
            # path when the caller kills FFmpeg right after grabbing the one
            # frame it asked for, so it is expected → DEBUG. A positive
            # non-zero exit code is a genuine FFmpeg failure → WARNING.
            # (rc is None only when the process is still running, which can't
            # happen after communicate() returned — treat that as anomalous.)
            log = _LOGGER.debug if (rc is not None and rc < 0) else _LOGGER.warning
            log(
                "fetch_mjpeg_snapshot: FFmpeg exited with code %s for %s — %s",
                rc,
                cam_host,
                err_text,
            )
            return None

        if not out:
            _LOGGER.warning(
                "fetch_mjpeg_snapshot: FFmpeg returned empty output for %s", cam_host
            )
            return None

        # Sanity-check: output must look like a JPEG
        if not out.startswith(_JPEG_MAGIC):
            _LOGGER.warning(
                "fetch_mjpeg_snapshot: output does not start with JPEG magic "
                "(got %s) for %s — discarding",
                out[:4].hex(),
                cam_host,
            )
            return None

        _LOGGER.debug(
            "fetch_mjpeg_snapshot: %d bytes in %.1f ms for %s",
            len(out),
            elapsed_ms,
            cam_host,
        )
        return out

    except TimeoutError:
        elapsed_ms = (time.monotonic() - t0) * 1000
        _LOGGER.warning(
            "fetch_mjpeg_snapshot: timeout after %.1f ms for %s",
            elapsed_ms,
            cam_host,
        )
        return None
    except FileNotFoundError:
        # ffmpeg binary not found — should never happen in HA but be safe
        _LOGGER.error(
            "fetch_mjpeg_snapshot: ffmpeg not found — cannot capture MJPEG snapshot"
        )
        return None
    except OSError as err:
        _LOGGER.warning("fetch_mjpeg_snapshot: OS error spawning ffmpeg: %s", err)
        return None
    finally:
        # BUG-1 fix: always reap the subprocess on any exception path
        # (TimeoutError, CancelledError, BaseException, etc.) to prevent
        # zombie FFmpeg processes accumulating under HA task cancellation.
        # FileNotFoundError / OSError mean proc was never created → guard.
        if proc is not None:
            try:
                proc.kill()
            except OSError:
                # ProcessLookupError (process already exited) is the common case.
                # Broader OSError (e.g. PermissionError) is caught too so it never
                # masks the original exception propagating from the try block.
                pass
            try:
                await proc.wait()
            except OSError:
                pass

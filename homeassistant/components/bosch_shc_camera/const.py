"""Constants for the Bosch Smart Home Camera integration."""

import re

DOMAIN = "bosch_shc_camera"

CLOUD_API = "https://residential.cbs.boschsecurity.com"

# Bounded slow-tier defer. See slow_tier.py.
SLOW_TIER_MAX_DEFER_SEC = 1800.0

# ── snap.jpg resolution (`JpegSize`) ──────────────────────────────────────────
# Every snap.jpg call site used to hardcode JpegSize=1206 (full resolution),
# including the ones serving the Lovelace card — which asks HA for width=315.
# Measured payloads for the same frame on one Gen1 outdoor camera:
#
#     JpegSize=1206  ≈ 500 KB      JpegSize=640  ≈ 220 KB      JpegSize=320  ≈ 65 KB
#
# On a bandwidth-constrained link the full-res body alone can take longer than
# HA's CAMERA_IMAGE_TIMEOUT (10 s), so a preview request fails outright and the
# card shows a stale frame. Deriving the size from the width HA passed to
# async_camera_image() costs nothing for callers that want full resolution:
# jpeg_size_for_width() returns None (= "leave it at JPEG_SIZE_FULL") whenever
# no width was requested, which is what the background image refresh, the
# image.* entity and the AI-analysis fetch do.
JPEG_SIZE_FULL = 1206
JPEG_SIZE_THUMB = 320
JPEG_SIZE_MEDIUM = 640

_JPEG_SIZE_RE = re.compile(r"JpegSize=\d+")


def jpeg_size_for_width(width: int | None) -> int | None:
    """Map the width HA requested onto a camera ``JpegSize`` value.

    Returns ``None`` when the caller did not ask for a thumbnail-sized image,
    meaning the snap.jpg URL should keep its full-resolution ``JpegSize``.
    """
    if width is None or width <= 0 or width > JPEG_SIZE_MEDIUM:
        return None
    if width <= JPEG_SIZE_THUMB:
        return JPEG_SIZE_THUMB
    return JPEG_SIZE_MEDIUM


def with_jpeg_size(url: str, size: int | None) -> str:
    """Return ``url`` with its ``JpegSize`` query parameter set to ``size``.

    A ``size`` of ``None`` (no width requested) returns the URL unchanged, so
    full-resolution callers keep exactly the URL they had before.
    """
    if not url or not size:
        return url
    if "JpegSize=" in url:
        return _JPEG_SIZE_RE.sub(f"JpegSize={int(size)}", url)
    return f"{url}{'&' if '?' in url else '?'}JpegSize={int(size)}"


# ── Network timeouts (seconds) ────────────────────────────────────────────────
# Centralised so snap + PUT /connection paths stay consistent across the
# integration and match the Python CLI (bosch_camera.py). Other endpoints
# still use inline literals — only the hot paths below were previously
# inconsistent (CLI 5/15s vs. integration 10s).
TIMEOUT_SNAP = 10  # GET on signed image / imageUrl
TIMEOUT_PUT_CONNECTION = 10  # PUT /v11/video_inputs/{id}/connection

# Requested session lifetime for the LOCAL RTSP stream (local_stream.py),
# substituted into the `rtsp_tunnel` URL's `maxSessionDuration` parameter.
# This minimal, snapshot-first build has no renewal/rebuild path, so a
# session that outlives this value simply ends and the entity reports no
# stream source until the integration is reloaded.
LOCAL_STREAM_MAX_SESSION_DURATION_SEC = 3600
TIMEOUT_RCP_099E_PROBE = 2.5  # RCP 0x099e thumbnail probe (GitHub #56 — must not eat the snap.jpg leg's budget)
RCP_099E_PROBE_FAILURE_MEMO_SEC = (
    3600  # skip the probe for this long per-cam_id after a failure/timeout
)

# GitHub #55: LOCAL snap.jpg's inline Digest request is capped at 6s to stay
# under HA's outer 10s CAMERA_IMAGE_TIMEOUT — too tight for cameras whose TLS
# handshake alone runs 2.5-6.9s, and a handshake killed mid-flight never gets
# pooled, so every request starts cold and hits the same wall. On a timeout,
# a background attempt gets this much more generous budget to complete the
# handshake once and leave a warm pooled connection for subsequent inline
# requests, rate-limited so a persistently-slow camera isn't hammered.
LOCAL_SNAP_WARMUP_TIMEOUT_SEC = 25.0
LOCAL_SNAP_WARMUP_MIN_INTERVAL_SEC = 30.0

# GET /v11/video_inputs (camera_list.py) — first call of every coordinator
# tick, gating everything else that tick. A bare timeout here used to fail
# the WHOLE tick immediately (community report, forum thread, 2026-07-23: a
# brief Bosch-cloud blip caused two consecutive failed ticks, self-recovered
# on the third) — one quick in-tick retry absorbs a momentary hiccup instead
# of costing users a full failed update + stale/offline-looking cameras over
# what a few seconds' grace would have covered. A persistent outage still
# fails after the retry, same as before.
TIMEOUT_VIDEO_INPUTS = 15.0
VIDEO_INPUTS_RETRY_DELAY_SEC = 3.0

# issue #47: AUTO-mode TCP pre-check chicken-and-egg breaker. When the
# camera's cached LAN IP is stale (DHCP re-lease after a mesh flap/reboot),
# every pre-check ping against it fails forever, which would otherwise skip
# LOCAL — and only the LOCAL PUT itself can teach us the camera's *current*
# IP. At most once per this interval, ignore a failing pre-check and let
# LOCAL be attempted for real so a fresh IP has a chance to be learned; the
# existing pre-warm-failure fallback still demotes to REMOTE gracefully if
# the camera really is unreachable.
LAN_RECHECK_FORCE_INTERVAL_SEC = 600.0

# SHC local-API fallback retry policy — offline circuit breaker for the
# coordinator's own local-API probing (privacy-mode cache read used by the
# snapshot fallback chain).
SHC_MAX_FAILS = 3  # mark SHC offline after this many consecutive failures
SHC_RETRY_INTERVAL = 120  # seconds — retry SHC after this long while offline

DEFAULT_OPTIONS = {
    "scan_interval": 60,
    "interval_status": 300,
    "interval_events": 300,
    "snapshot_interval": 1800,
    "enable_snapshots": True,
    "stream_connection_type": "local",
}

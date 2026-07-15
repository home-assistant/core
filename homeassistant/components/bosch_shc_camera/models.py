"""Camera model definitions and timing configurations.

Each Bosch Smart Home camera model has different hardware characteristics
that affect stream startup, encoder warm-up, and session management.
All timing values are empirically measured and model-specific.

Supported models (Gen1, firmware 7.91.56):
  - "360 Innenkamera"   (API: INDOOR / CAMERA_360)
  - "Eyes Außenkamera"   (API: OUTDOOR / CAMERA_EYES)

Supported models (Gen2, firmware 9.40.25):
  - "Eyes Außenkamera II"  (API: HOME_Eyes_Outdoor / CAMERA_OUTDOOR_GEN2)
  - "Eyes Innenkamera II"  (API: HOME_Eyes_Indoor / CAMERA_INDOOR_GEN2)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CameraModelConfig:
    """Timing and behavior configuration for a specific camera model."""

    # ── Display ──────────────────────────────────────────────────────────
    display_name: str  # Official Bosch product name
    generation: int = 1  # Hardware generation (1 or 2)

    # ── Pre-warm (RTSP DESCRIBE to wake H.264 encoder) ───────────────────
    pre_warm_delay: int = (
        2  # Seconds to wait after PUT /connection before first DESCRIBE
    )
    pre_warm_retries: int = 5  # Max DESCRIBE attempts before giving up
    pre_warm_retry_wait: int = 3  # Seconds between failed DESCRIBE attempts
    post_warm_buffer: int = 3  # Seconds to wait after successful DESCRIBE (TLS cleanup)
    describe_timeout: int = 5  # Timeout per DESCRIBE read (seconds)

    # ── Stream startup ───────────────────────────────────────────────────
    min_total_wait: int = (
        30  # Minimum seconds from PUT /connection until RTSP URL exposed
    )
    # Ensures encoder produces valid H.264 frames.
    # For renewals: 2/3 of this value is used (camera already warm).

    # ── Session management ───────────────────────────────────────────────
    renewal_interval: int = 500  # Seconds between auto-renewal cycles.
    # Camera accepts maxSessionDuration=3600 in RTSP URL,
    # but some models reset the connection earlier.
    max_session_duration: int = (
        3600  # Value sent in RTSP URL maxSessionDuration parameter.
    )
    heartbeat_interval: int = (
        30  # Seconds between PUT /connection heartbeats during LOCAL stream.
    )
    # Bosch app uses ~1s. Outdoor needs more aggressive keepalive.

    # ── Fallback / error recovery ────────────────────────────────────────
    # Consecutive FFmpeg errors before AUTO mode falls back to REMOTE.
    # Bumped from a flat 3 to per-model values in v10.5.4: with the active-
    # promotion + counter-decay self-heal in place, false fallbacks recover
    # automatically, so the gradual-counter path can be more tolerant before
    # giving up on LOCAL. Indoor cameras are stable on a wired-equivalent
    # WLAN and rarely produce real bursts; outdoor cameras see real WLAN
    # flakiness + slower encoder init and benefit from a higher tolerance.
    # The watchdog's hard 120 s "no healthy HLS output" path is unaffected
    # — it still forces fallback regardless of this counter.
    max_stream_errors: int = 5
    min_wifi_for_local: int = (
        40  # Minimum WiFi signal % to attempt LOCAL (below → use REMOTE)
    )

    # ── Snapshots ────────────────────────────────────────────────────────
    snapshot_warmup: int = 4  # Seconds to wait before LOCAL snap.jpg fetch
    # (encoder must be running for fresh frame)
    event_refresh_delay: float = 1.5  # Seconds to wait before fetching a fresh snap
    # in response to an FCM motion/person event.
    # Gen2 cams capture immediately → set to 0;
    # Gen1 needs ~1.5 s to settle the encoder so
    # the snap reflects the post-trigger frame.


# ── Model registry ───────────────────────────────────────────────────────
# Keyed by API hardwareVersion values from GET /v11/video_inputs response.

MODELS: dict[str, CameraModelConfig] = {
    # ── Gen1 Indoor: 360 Innenkamera ─────────────────────────────────────
    # Faster SoC, encoder ready in ~5s, pre-warm usually succeeds on 1st attempt.
    # Session stable for 3500s+ (tested 90s+ without renewal, no disconnect).
    "INDOOR": CameraModelConfig(
        display_name="360 Innenkamera",
        generation=1,
        pre_warm_delay=1,
        pre_warm_retries=3,
        pre_warm_retry_wait=3,
        post_warm_buffer=2,
        describe_timeout=5,
        min_total_wait=25,
        renewal_interval=3500,
        max_session_duration=3600,
        heartbeat_interval=30,
        snapshot_warmup=3,
    ),
    # ── Gen1 Outdoor: Eyes Außenkamera ────────────────────────────────────
    # Slower encoder init (~25s), pre-warm needs 3-4 DESCRIBE attempts.
    # Previously dropped connections after 2-10 min without heartbeat.
    # Now stable with 10s heartbeat (PUT /connection) + FFmpeg GET_PARAMETER
    # + TCP keep-alive on proxy sockets. Tested 2:20+ without renewal.
    # renewal_interval=3500 — no proactive renewal needed. Heartbeat keeps
    # session alive. Proactive renewal causes HLS interruptions + pipe errors.
    # Emergency renewal still triggers after 3 consecutive heartbeat failures.
    # heartbeat_interval=10 — aggressive cloud keepalive (Bosch app uses ~1s).
    "OUTDOOR": CameraModelConfig(
        display_name="Eyes Außenkamera",
        generation=1,
        pre_warm_delay=2,
        pre_warm_retries=8,
        pre_warm_retry_wait=5,
        post_warm_buffer=3,
        describe_timeout=8,
        min_total_wait=35,
        renewal_interval=3500,
        max_session_duration=3600,
        heartbeat_interval=10,
        snapshot_warmup=5,
        max_stream_errors=10,  # outdoor: real WLAN flap + slower encoder
    ),
}

# Legacy API values map to the same configs
MODELS["CAMERA_360"] = MODELS["INDOOR"]
MODELS["CAMERA_EYES"] = MODELS["OUTDOOR"]

# ── Gen2: Eyes Außenkamera II ────────────────────────────────────────────
# API hardwareVersion: "HOME_Eyes_Outdoor" (confirmed by user DrNiKa, FW 9.40.25)
# App product type: "CAMERA_OUTDOOR_GEN2" (from Bosch product catalog)
# FW 9.40.25 enforces a hard 60-second LOCAL session cap — the camera resets
# the RTSP TCP connection ~63s after PUT /connection regardless of the URL's
# maxSessionDuration parameter. Proactive renewal must fire before the cut so
# a fresh session is pre-warmed and Stream.update_source() can swap URLs
# before the old session dies. 50s gives ~13s of headroom (renewal ~23s for
# Gen2 Outdoor with min_total_wait=35, pre_warm uses 2/3 of that on renewal).
MODELS["HOME_Eyes_Outdoor"] = CameraModelConfig(
    display_name="Eyes Außenkamera II",
    generation=2,
    pre_warm_delay=2,
    pre_warm_retries=8,
    pre_warm_retry_wait=5,
    post_warm_buffer=3,
    describe_timeout=8,
    min_total_wait=35,
    # Both keepalive intervals disabled: on Gen2 Outdoor FW 9.40.25 every
    # PUT /connection LOCAL (whether heartbeat or renewal) rotates the
    # ephemeral Digest credentials on the camera, which invalidates the live
    # RTSP session bound to the old creds. FFmpeg then sees either
    # "Operation timed out finding first packet" (heartbeat) or
    # "Connection reset by peer" + 401 on reconnect (renewal). FFmpeg already
    # sends RTSP GET_PARAMETER every ~15s which refreshes the camera-side
    # RTSP session timeout without cred rotation — that is the ONLY keepalive
    # that doesn't kill the stream. The loop still runs with a long 3600 s
    # tick so the emergency-renewal path (3 consecutive heartbeat failures)
    # stays wired up in case of a true network outage.
    renewal_interval=3600,
    max_session_duration=3600,
    heartbeat_interval=3600,
    snapshot_warmup=5,
    max_stream_errors=10,  # outdoor: real WLAN flap + slower encoder
    event_refresh_delay=0,  # Gen2 captures immediately, no settle delay needed
)
MODELS["CAMERA_OUTDOOR_GEN2"] = MODELS["HOME_Eyes_Outdoor"]

# ── Gen2: Eyes Innenkamera II ────────────────────────────────────────────
# API hardwareVersion: "HOME_Eyes_Indoor" (confirmed live on cam 22222222, FW 9.40.25)
# App product type: "CAMERA_INDOOR_GEN2"
# FW 9.40.25 on Indoor exhibits the same destructive PUT /connection behaviour
# as Outdoor: every heartbeat rotates Digest credentials, which invalidates the
# live RTSP session and forces FFmpeg to TEARDOWN + reconnect — visible as
# flicker + green YUV-garbage block while the new keyframe arrives. FFmpeg's
# native GET_PARAMETER every ~15s already keeps the RTSP session alive without
# rotation, so disabling the destructive heartbeat is safe.
MODELS["HOME_Eyes_Indoor"] = CameraModelConfig(
    display_name="Eyes Innenkamera II",
    generation=2,
    pre_warm_delay=1,
    pre_warm_retries=3,
    pre_warm_retry_wait=3,
    post_warm_buffer=2,
    describe_timeout=5,
    min_total_wait=25,
    renewal_interval=3600,
    max_session_duration=3600,
    heartbeat_interval=3600,
    snapshot_warmup=3,
    event_refresh_delay=0,
)
MODELS["CAMERA_INDOOR_GEN2"] = MODELS["HOME_Eyes_Indoor"]


# Default for unknown models
DEFAULT_MODEL = CameraModelConfig(
    display_name="Unknown Camera",
    generation=1,
    pre_warm_delay=2,
    pre_warm_retries=5,
    pre_warm_retry_wait=3,
    post_warm_buffer=3,
    describe_timeout=5,
    min_total_wait=30,
    renewal_interval=3500,
    max_session_duration=3600,
    heartbeat_interval=15,
    snapshot_warmup=4,
)


def get_model_config(hw_version: str) -> CameraModelConfig:
    """Return model config for a hardwareVersion string."""
    return MODELS.get(hw_version, DEFAULT_MODEL)


def get_display_name(hw_version: str) -> str:
    """Return human-readable model name for a hardwareVersion string."""
    cfg = MODELS.get(hw_version)
    if cfg:
        return cfg.display_name
    # Dynamic fallback for unknown models
    hw_lower = hw_version.lower()
    if "indoor" in hw_lower or "360" in hw_lower:
        return f"Innenkamera ({hw_version})"
    if "outdoor" in hw_lower or "eyes" in hw_lower:
        return f"Außenkamera ({hw_version})"
    return hw_version  # raw value as last resort

"""Camera model definitions.

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
    """Display/generation identity for a specific camera model.

    This snapshot-only build has no live-stream session management, so it
    only needs the two fields platform code actually reads — `generation`
    (Gen1 vs Gen2 behavior branches) and `display_name`. A prior version
    also carried pre-warm/RTSP-session/heartbeat/stream-error timing
    fields left over from before this integration's scope was reduced to
    snapshot-only; none of them had any call site in this tree (Copilot
    review round 7).
    """

    display_name: str  # Official Bosch product name
    generation: int = 1  # Hardware generation (1 or 2)


# ── Model registry ───────────────────────────────────────────────────────
# Keyed by API hardwareVersion values from GET /v11/video_inputs response.

MODELS: dict[str, CameraModelConfig] = {
    "INDOOR": CameraModelConfig(display_name="360 Innenkamera", generation=1),
    "OUTDOOR": CameraModelConfig(display_name="Eyes Außenkamera", generation=1),
}

# Legacy API values map to the same configs
MODELS["CAMERA_360"] = MODELS["INDOOR"]
MODELS["CAMERA_EYES"] = MODELS["OUTDOOR"]

# API hardwareVersion: "HOME_Eyes_Outdoor" (confirmed by user DrNiKa, FW 9.40.25)
# App product type: "CAMERA_OUTDOOR_GEN2" (from Bosch product catalog)
MODELS["HOME_Eyes_Outdoor"] = CameraModelConfig(
    display_name="Eyes Außenkamera II", generation=2
)
MODELS["CAMERA_OUTDOOR_GEN2"] = MODELS["HOME_Eyes_Outdoor"]

# API hardwareVersion: "HOME_Eyes_Indoor" (confirmed live on cam 22222222, FW 9.40.25)
# App product type: "CAMERA_INDOOR_GEN2"
MODELS["HOME_Eyes_Indoor"] = CameraModelConfig(
    display_name="Eyes Innenkamera II", generation=2
)
MODELS["CAMERA_INDOOR_GEN2"] = MODELS["HOME_Eyes_Indoor"]


# Default for unknown models
DEFAULT_MODEL = CameraModelConfig(display_name="Unknown Camera", generation=1)


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

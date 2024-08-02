"""Utilities for the LinkPlay component."""

from typing import Final

MANUFACTURER_ARTSOUND: Final[str] = "ArtSound"
MANUFACTURER_ARYLIC: Final[str] = "Arylic"
MANUFACTURER_IEAST: Final[str] = "iEAST"
MANUFACTURER_GENERIC: Final[str] = "Generic"
MODELS_ARTSOUND_SMART_ZONE4: Final[str] = "Smart Zone 4 AMP"
MODELS_ARTSOUND_SMART_HYDE: Final[str] = "Smart Hyde"
MODELS_ARYLIC_S50: Final[str] = "S50+"
MODELS_ARYLIC_S50_PRO: Final[str] = "S50 Pro"
MODELS_ARYLIC_A30: Final[str] = "A30"
MODELS_ARYLIC_A50S: Final[str] = "A50+"
MODELS_ARYLIC_UP2STREAM_AMP_V3: Final[str] = "Up2Stream Amp v3"
MODELS_ARYLIC_UP2STREAM_AMP_V4: Final[str] = "Up2Stream Amp v4"
MODELS_ARYLIC_UP2STREAM_PRO_V3: Final[str] = "Up2Stream Pro v3"
MODELS_IEAST_AUDIOCAST_M5: Final[str] = "AudioCast M5"
MODELS_GENERIC: Final[str] = "Generic"


def get_info_from_project(project: str) -> tuple[str, str]:
    """Get manufacturer and model info based on given project."""
    match project:
        case "SMART_ZONE4_AMP":
            return MANUFACTURER_ARTSOUND, MODELS_ARTSOUND_SMART_ZONE4
        case "SMART_HYDE":
            return MANUFACTURER_ARTSOUND, MODELS_ARTSOUND_SMART_HYDE
        case "ARYLIC_S50":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_S50
        case "RP0016_S50PRO_S":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_S50_PRO
        case "RP0011_WB60_S":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_A30
        case "ARYLIC_A50S":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_A50S
        case "UP2STREAM_AMP_V3":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_UP2STREAM_AMP_V3
        case "UP2STREAM_AMP_V4":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_UP2STREAM_AMP_V4
        case "UP2STREAM_PRO_V3":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_UP2STREAM_PRO_V3
        case "iEAST-02":
            return MANUFACTURER_IEAST, MODELS_IEAST_AUDIOCAST_M5
        case _:
            return MANUFACTURER_GENERIC, MODELS_GENERIC

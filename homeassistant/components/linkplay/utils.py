"""Utilities for the LinkPlay component."""

from typing import Final

MANUFACTURER_ARTSOUND: Final[str] = "ArtSound"
MANUFACTURER_ARYLIC: Final[str] = "Arylic"
MANUFACTURER_GENERIC: Final[str] = "Generic"
MODELS_ARTSOUND_SMART_ZONE4: Final[str] = "Smart Zone 4 AMP"
MODELS_ARYLIC_SMART_HYDE: Final[str] = "Smart Hyde"
MODELS_ARYLIC_S50_PRO: Final[str] = "S50 Pro"
MODELS_ARYLIC_A30: Final[str] = "A30"
MODELS_GENERIC: Final[str] = "Generic"


def get_info_from_project(project: str) -> tuple[str, str]:
    """Get manufacturer and model info based on given project."""
    match project:
        case "SMART_ZONE4_AMP":
            return MANUFACTURER_ARTSOUND, MODELS_ARTSOUND_SMART_ZONE4
        case "SMART_HYDE":
            return MANUFACTURER_ARTSOUND, MODELS_ARTSOUND_SMART_HYDE
        case "RP0016_S50PRO_S":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_S50_PRO
        case "RP0011_WB60_S":
            return MANUFACTURER_ARYLIC, MODELS_ARYLIC_A30
        case _:
            return MANUFACTURER_GENERIC, MODELS_GENERIC

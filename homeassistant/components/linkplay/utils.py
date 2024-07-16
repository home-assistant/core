"""Utilities for the LinkPlay component."""

from typing import Final

MANUFACTURER_ARTSOUND: Final[str] = "ArtSound"
MANUFACTURER_GENERIC: Final[str] = "Generic"
MODELS_ARTSOUND_SMART_ZONE4: Final[str] = "Smart Zone 4 AMP"
MODELS_ARTSOUND_SMART_HYDE: Final[str] = "Smart Hyde"
MODELS_GENERIC: Final[str] = "Generic"


def get_info_from_project(project: str) -> tuple[str, str]:
    """Get manufacturer and model info based on given project."""
    match project:
        case "SMART_ZONE4_AMP":
            return MANUFACTURER_ARTSOUND, MODELS_ARTSOUND_SMART_ZONE4
        case "SMART_HYDE":
            return MANUFACTURER_ARTSOUND, MODELS_ARTSOUND_SMART_HYDE
        case _:
            return MANUFACTURER_GENERIC, MODELS_GENERIC

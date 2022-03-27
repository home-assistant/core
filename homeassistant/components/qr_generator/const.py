"""Constants for the QR Generator integration."""
from __future__ import annotations

from logging import Logger, getLogger

_LOGGER: Logger = getLogger(__package__)

DOMAIN: str = "qr_generator"

# Regex to mach color with the #RRGGBBAA format and it short forms
HEX_COLOR_REGEX: str = (
    r"^#([A-Fa-f0-9]{6}|[A-Fa-f0-9]{3}|[A-Fa-f0-9]{4}|[A-Fa-f0-9]{8})$"
)

ERROR_CORRECTION_LEVEL = ["L", "M", "Q", "H"]

CONF_COLOR: str = "color"
CONF_SCALE: str = "scale"
CONF_BORDER: str = "border"
CONF_ADVANCED: str = "advanced"
CONF_ERROR_CORRECTION: str = "error_correction"
CONF_BACKGROUND_COLOR: str = "background_color"

DEFAULT_COLOR: str = "#000000"
DEFAULT_SCALE: int = 10
DEFAULT_BORDER: int = 2
DEFAULT_ERROR_CORRECTION: str = "H"
DEFAULT_BACKGROUND_COLOR: str = "#FFFFFF"

ATTR_TEXT: str = "text"
ATTR_COLOR: str = CONF_COLOR
ATTR_SCALE: str = CONF_SCALE
ATTR_BORDER: str = CONF_BORDER
ATTR_ERROR_CORRECTION: str = CONF_ERROR_CORRECTION
ATTR_BACKGROUND_COLOR: str = CONF_BACKGROUND_COLOR

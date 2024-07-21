"""Constants for the madvr-envy integration."""

from collections.abc import Iterable
from enum import Enum

DOMAIN = "madvr"

DEFAULT_NAME = "envy"
DEFAULT_PORT = 44077

# Sensor keys
TEMP_GPU = "temp_gpu"
TEMP_HDMI = "temp_hdmi"
TEMP_CPU = "temp_cpu"
TEMP_MAINBOARD = "temp_mainboard"
INCOMING_RES = "incoming_res"
INCOMING_SIGNAL_TYPE = "incoming_signal_type"
INCOMING_FRAME_RATE = "incoming_frame_rate"
INCOMING_COLOR_SPACE = "incoming_color_space"
INCOMING_BIT_DEPTH = "incoming_bit_depth"
INCOMING_COLORIMETRY = "incoming_colorimetry"
INCOMING_BLACK_LEVELS = "incoming_black_levels"
INCOMING_ASPECT_RATIO = "incoming_aspect_ratio"
OUTGOING_RES = "outgoing_res"
OUTGOING_SIGNAL_TYPE = "outgoing_signal_type"
OUTGOING_FRAME_RATE = "outgoing_frame_rate"
OUTGOING_COLOR_SPACE = "outgoing_color_space"
OUTGOING_BIT_DEPTH = "outgoing_bit_depth"
OUTGOING_COLORIMETRY = "outgoing_colorimetry"
OUTGOING_BLACK_LEVELS = "outgoing_black_levels"
ASPECT_RES = "aspect_res"
ASPECT_DEC = "aspect_dec"
ASPECT_INT = "aspect_int"
ASPECT_NAME = "aspect_name"
MASKING_RES = "masking_res"
MASKING_DEC = "masking_dec"
MASKING_INT = "masking_int"


# Button Commands
class ButtonCommands(Enum):
    """Enum for madvr button commands and names."""

    reset_temporary = ["ResetTemporary"]
    openmenu_info = ["OpenMenu", "Info"]
    openmenu_settings = ["OpenMenu", "Settings"]
    openmenu_configuration = ["OpenMenu", "Configuration"]
    openmenu_profiles = ["OpenMenu", "Profiles"]
    openmenu_testpatterns = ["OpenMenu", "TestPatterns"]
    toggle_tonemap = ["Toggle", "ToneMap"]
    toggle_highlightrecovery = ["Toggle", "HighlightRecovery"]
    toggle_contrastrecovery = ["Toggle", "ContrastRecovery"]
    toggle_shadowrecovery = ["Toggle", "ShadowRecovery"]
    toggle_3dlut = ["Toggle", "_3DLUT"]
    toggle_screenboundaries = ["Toggle", "ScreenBoundaries"]
    toggle_histogram = ["Toggle", "Histogram"]
    toggle_debugosd = ["Toggle", "DebugOSD"]
    refresh_licenseinfo = ["RefreshLicenseInfo"]
    force1080p60output = ["Force1080p60Output"]
    button_left = ["KeyPress", "LEFT"]
    button_right = ["KeyPress", "RIGHT"]
    button_up = ["KeyPress", "UP"]
    button_down = ["KeyPress", "DOWN"]
    button_ok = ["KeyPress", "OK"]
    button_back = ["KeyPress", "BACK"]
    button_red = ["KeyPress", "RED"]
    button_green = ["KeyPress", "GREEN"]
    button_blue = ["KeyPress", "BLUE"]
    button_yellow = ["KeyPress", "YELLOW"]
    button_magenta = ["KeyPress", "MAGENTA"]
    button_cyan = ["KeyPress", "CYAN"]

    def __init__(self, value: list[str]) -> None:
        """Initialize the command enum."""
        self._value_ = value

    @property
    def value(self) -> Iterable[str]:
        """Return the command value."""
        return self._value_

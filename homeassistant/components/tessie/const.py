"""Constants used by Tessie integration."""
from __future__ import annotations

from enum import StrEnum

DOMAIN = "tessie"

MODELS = {
    "model3": "Model 3",
    "modelx": "Model X",
    "modely": "Model Y",
    "models": "Model S",
}


class TessieApi(StrEnum):
    """API response keys for Tessie."""

    CHARGE_STATE = "charge_state"
    CLIMATE_STATE = "climate_state"
    DRIVE_STATE = "drive_state"
    GUI_SETTINGS = "gui_settings"
    VEHICLE_CONFIG = "vehicle_config"
    VEHICLE_STATE = "vehicle_state"
    VEHICLE_STATE_MEDIA_INFO = "media_info"
    VEHICLE_STATE_MEDIA_STATE = "media_state"
    VEHICLE_STATE_SOFTWARE_UPDATE = "software_update"
    VEHICLE_STATE_SPEED_LIMIT_MODE = "speed_limit_mode"
    DISPLAY_NAME = "display_name"

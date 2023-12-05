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


class TessieStatus(StrEnum):
    """Tessie status."""

    ASLEEP = "asleep"
    ONLINE = "online"
    OFFLINE = "offline"


class TessieKey(StrEnum):
    """API response keys in the root."""

    VIN = "vin"
    STATE = "state"
    DISPLAY_NAME = "display_name"
    API_VERSION = "api_version"


class TessieCategory(StrEnum):
    """API response groups ."""

    CHARGE_STATE = "charge_state"
    CLIMATE_STATE = "climate_state"
    DRIVE_STATE = "drive_state"
    GUI_SETTINGS = "gui_settings"
    VEHICLE_CONFIG = "vehicle_config"
    VEHICLE_STATE = "vehicle_state"


class TessieVehicleStateCategory(StrEnum):
    """API response groups under vehicle_state."""

    MEDIA_INFO = "media_info"
    MEDIA_STATE = "media_state"
    SOFTWARE_UPDATE = "software_update"
    SPEED_LIMIT_MODE = "speed_limit_mode"

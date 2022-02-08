"""Constants for the Overkiz (by Somfy) integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from pyoverkiz.enums import OverkizCommandParam, UIClass, UIWidget

from homeassistant.const import Platform

DOMAIN: Final = "overkiz"
LOGGER: logging.Logger = logging.getLogger(__package__)

CONF_HUB: Final = "hub"
DEFAULT_HUB: Final = "somfy_europe"

UPDATE_INTERVAL: Final = timedelta(seconds=30)
UPDATE_INTERVAL_ALL_ASSUMED_STATE: Final = timedelta(minutes=60)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.COVER,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SCENE,
    Platform.SENSOR,
    Platform.SWITCH,
]

IGNORED_OVERKIZ_DEVICES: list[UIClass | UIWidget] = [
    UIClass.PROTOCOL_GATEWAY,
    UIClass.POD,
]

# Used to map the Somfy widget and ui_class to the Home Assistant platform
OVERKIZ_DEVICE_TO_PLATFORM: dict[UIClass | UIWidget, Platform] = {
    UIClass.ADJUSTABLE_SLATS_ROLLER_SHUTTER: Platform.COVER,
    UIClass.AWNING: Platform.COVER,
    UIClass.CURTAIN: Platform.COVER,
    UIClass.DOOR_LOCK: Platform.LOCK,
    UIClass.EXTERIOR_SCREEN: Platform.COVER,
    UIClass.EXTERIOR_VENETIAN_BLIND: Platform.COVER,
    UIClass.GARAGE_DOOR: Platform.COVER,
    UIClass.GATE: Platform.COVER,
    UIClass.LIGHT: Platform.LIGHT,
    UIClass.ON_OFF: Platform.SWITCH,
    UIClass.PERGOLA: Platform.COVER,
    UIClass.ROLLER_SHUTTER: Platform.COVER,
    UIClass.SCREEN: Platform.COVER,
    UIClass.SHUTTER: Platform.COVER,
    UIClass.SWIMMING_POOL: Platform.SWITCH,
    UIClass.SWINGING_SHUTTER: Platform.COVER,
    UIClass.VENETIAN_BLIND: Platform.COVER,
    UIClass.WINDOW: Platform.COVER,
    UIWidget.DOMESTIC_HOT_WATER_TANK: Platform.SWITCH,  # widgetName, uiClass is WaterHeatingSystem (not supported)
    UIWidget.MY_FOX_SECURITY_CAMERA: Platform.COVER,  # widgetName, uiClass is Camera (not supported)
    UIWidget.RTD_INDOOR_SIREN: Platform.SWITCH,  # widgetName, uiClass is Siren (not supported)
    UIWidget.RTD_OUTDOOR_SIREN: Platform.SWITCH,  # widgetName, uiClass is Siren (not supported)
    UIWidget.RTS_GENERIC: Platform.COVER,  # widgetName, uiClass is Generic (not supported)
    UIWidget.STATELESS_ALARM_CONTROLLER: Platform.SWITCH,  # widgetName, uiClass is Alarm (not supported)
    UIWidget.STATELESS_EXTERIOR_HEATING: Platform.SWITCH,  # widgetName, uiClass is ExteriorHeatingSystem (not supported)
}

# Map Overkiz camelCase to Home Assistant snake_case for translation
OVERKIZ_STATE_TO_TRANSLATION: dict[str, str] = {
    OverkizCommandParam.EXTERNAL_GATEWAY: "external_gateway",
    OverkizCommandParam.LOCAL_USER: "local_user",
    OverkizCommandParam.LOW_BATTERY: "low_battery",
    OverkizCommandParam.LSC: "lsc",
    OverkizCommandParam.MAINTENANCE_REQUIRED: "maintenance_required",
    OverkizCommandParam.NO_DEFECT: "no_defect",
    OverkizCommandParam.SAAC: "saac",
    OverkizCommandParam.SFC: "sfc",
    OverkizCommandParam.UPS: "ups",
}

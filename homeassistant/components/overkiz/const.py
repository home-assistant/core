"""Constants for the Overkiz (by Somfy) integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Final

from pyoverkiz.enums import UIClass
from pyoverkiz.enums.ui import UIWidget

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
    UIClass.DOOR_LOCK: Platform.LOCK,
    UIWidget.DOMESTIC_HOT_WATER_TANK: Platform.SWITCH,  # widgetName, uiClass is WaterHeatingSystem (not supported)
    UIClass.LIGHT: Platform.LIGHT,
    UIClass.ON_OFF: Platform.SWITCH,
    UIWidget.RTD_INDOOR_SIREN: Platform.SWITCH,  # widgetName, uiClass is Siren (not supported)
    UIWidget.RTD_OUTDOOR_SIREN: Platform.SWITCH,  # widgetName, uiClass is Siren (not supported)
    UIClass.SWIMMING_POOL: Platform.SWITCH,
}

# Map Overkiz camelCase to Home Assistant snake_case for translation
OVERKIZ_STATE_TO_TRANSLATION: dict[str, str] = {
    "externalGateway": "external_gateway",
    "localUser": "local_user",
    "lowBattery": "low_battery",
    "LSC": "lsc",
    "maintenanceRequired": "maintenance_required",
    "noDefect": "no_defect",
    "SAAC": "saac",
    "SFC": "sfc",
    "UPS": "ups",
}

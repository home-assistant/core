"""
Module helps to strip aut unneeded properties.

map icons and classes to properties.
"""
from enum import Enum
import typing

from homeassistant.const import (
    DEVICE_CLASS_BATTERY,
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_TIMESTAMP,
    LENGTH_FEET,
    LENGTH_METERS,
    PERCENTAGE,
    TIME_HOURS,
    TIME_SECONDS,
)

from .const import ATTR_ICON, ATTR_PICTURE, ATTR_SWITCH, ATTR_TYPE, ATTR_UOM

IMOW_SENSORS_MAP: typing.Dict[str, typing.Dict] = {
    "asmEnabled": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: None,
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "automaticModeEnabled": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:arrow-decision-auto-outline",
        ATTR_SWITCH: True,
        ATTR_PICTURE: False,
    },
    "childLock": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:baby-carriage",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "circumference": {
        ATTR_TYPE: None,
        ATTR_UOM: LENGTH_METERS,
        ATTR_ICON: "mdi:go-kart-track",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "coordinateLatitude": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:map",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "coordinateLongitude": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:map",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "corridorMode": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:go-kart-track",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "demoModeEnabled": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:information-outline",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "deviceTypeDescription": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:robot-mower",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "edgeMowingMode": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:axis-arrow-info",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "energyMode": {
        ATTR_TYPE: DEVICE_CLASS_ENERGY,
        ATTR_UOM: None,
        ATTR_ICON: None,
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "firmwareVersion": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:information-outline",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "gpsProtectionEnabled": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:shield-check",
        ATTR_SWITCH: True,
        ATTR_PICTURE: False,
    },
    "lastWeatherCheck": {
        ATTR_TYPE: DEVICE_CLASS_TIMESTAMP,
        ATTR_UOM: None,
        ATTR_ICON: None,
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "ledStatus": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:lightbulb",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "machineError": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:lightning-bolt-outline",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "machineState": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:state-machine",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "mappingIntelligentHomeDrive": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:state-machine",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "mowerImageThumbnailUrl": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:file-image-outline",
        ATTR_SWITCH: False,
        ATTR_PICTURE: True,
    },
    "mowerImageUrl": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:file-image-outline",
        ATTR_SWITCH: False,
        ATTR_PICTURE: True,
    },
    "name": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:robot-mower",
        ATTR_SWITCH: False,
        ATTR_PICTURE: True,
    },
    "protectionLevel": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:shield-check",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "rainSensorMode": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:weather-pouring",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "smartLogic_dynamicMowingplan": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:lightbulb-on-outline",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "smartLogic_mowingAreaInMeter": {
        ATTR_TYPE: None,
        ATTR_UOM: LENGTH_METERS,
        ATTR_ICON: "mdi:lightbulb-on-outline",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "smartLogic_mowingAreaInFeet": {
        ATTR_TYPE: None,
        ATTR_UOM: LENGTH_FEET,
        ATTR_ICON: "mdi:lightbulb-on-outline",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "smartLogic_mowingGrowthAdjustment": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:lightbulb-on-outline",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "smartLogic_mowingTime": {
        ATTR_TYPE: None,
        ATTR_UOM: TIME_HOURS,
        ATTR_ICON: "mdi:watch",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "smartLogic_mowingTimeManual": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:lightbulb-on-outline",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "smartLogic_performedActivityTime": {
        ATTR_TYPE: None,
        ATTR_UOM: TIME_HOURS,
        ATTR_ICON: "mdi:watch",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "smartLogic_smartNotifications": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:cellphone-message",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "smartLogic_suggestedActivityTime": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:lightbulb-on-outline",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "smartLogic_weatherForecastEnabled": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:lightbulb-on-outline",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "smartLogic_softwarePacket": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:information-outline",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "stateMessage_error": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:message-text",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "stateMessage_long": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:message-text",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "stateMessage_short": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:message-text",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "softwarePacket": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:information-outline",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "statistics_totalBladeOperatingTime": {
        ATTR_TYPE: None,
        ATTR_UOM: TIME_SECONDS,
        ATTR_ICON: "mdi:watch",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "statistics_totalDistanceTravelled": {
        ATTR_TYPE: None,
        ATTR_UOM: LENGTH_METERS,
        ATTR_ICON: "mdi:map-marker-distance",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "statistics_totalOperatingTime": {
        ATTR_TYPE: None,
        ATTR_UOM: TIME_SECONDS,
        ATTR_ICON: "mdi:watch",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "status_bladeService": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:knife",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "status_chargeLevel": {
        ATTR_TYPE: DEVICE_CLASS_BATTERY,
        ATTR_UOM: PERCENTAGE,
        ATTR_ICON: None,
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "status_lastGeoPositionDate": {
        ATTR_TYPE: DEVICE_CLASS_TIMESTAMP,
        ATTR_UOM: None,
        ATTR_ICON: None,
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "status_lastSeenDate": {
        ATTR_TYPE: DEVICE_CLASS_TIMESTAMP,
        ATTR_UOM: None,
        ATTR_ICON: None,
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "status_online": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:antenna",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "status_rainStatus": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:weather-pouring",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "team": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:account-group",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "teamable": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:account-group",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "timeZone": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:map-clock-outline",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
    "version": {
        ATTR_TYPE: None,
        ATTR_UOM: None,
        ATTR_ICON: "mdi:information-outline",
        ATTR_SWITCH: False,
        ATTR_PICTURE: False,
    },
}

ENTITY_STRIP_OUT_PROPERTIES = [
    "status_extraStatus",
    "status_extraStatus1",
    "status_extraStatus2",
    "status_extraStatus3",
    "status_extraStatus4",
    "status_extraStatus5",
    "status_mainState",
    "status_mower",
    "smartLogic_mower",
    "stateMessage_errorId",
    "stateMessage_legacyMessage",
    "statistics_mower",
    "lastNoErrorMainState",
    "unitFormat",
    "imsi",
    "localTimezoneOffset",
    "accountId",
    "gdprAccepted",
    "endOfContract",
    "cModuleId",
    "externalId",
    "codePage",
    "boundryOffset",
    "deviceType",
    "id",
    "smartLogic_totalActivityActiveTime",
    "smartLogic_mowingArea",
    "status_lastNoErrorMainState",
    "imow",
]


class LANGUAGES(Enum):
    """Enum for languagecode mapping."""

    da = "Dansk"
    de = "Deutsch"
    en = "English"
    et = "Eesti"
    es = "Español"
    fr = "Français"
    hr = "Hrvatski"
    it = "Italiano"
    lv = "Latviešu"
    lt = "Lietuvių"
    hu = "Magyar"
    nl = "Nederlands"
    nb = "Norsk Bokmål"
    pl = "Polski"
    pt = "Português"
    ro = "Română"
    sk = "Slovenčina"
    sl = "Slovenščina"
    fi = "Suomi"
    sv = "Svenska"
    cs = "čeština"
    el = "ελληνικά"
    bg = "български"
    sr = "српски"
    ru = "русский"

"""Constants for LG ThinQ."""

# Base component constants.
from enum import StrEnum
from typing import Any, Final

from thinqconnect import (
    AirConditionerDevice,
    AirPurifierDevice,
    AirPurifierFanDevice,
    CeilingFanDevice,
    CooktopDevice,
    DehumidifierDevice,
    DeviceType,
    DishWasherDevice,
    DryerDevice,
    HomeBrewDevice,
    HoodDevice,
    HumidifierDevice,
    KimchiRefrigeratorDevice,
    MicrowaveOvenDevice,
    OvenDevice,
    PlantCultivatorDevice,
    RefrigeratorDevice,
    RobotCleanerDevice,
    StickCleanerDevice,
    StylerDevice,
    SystemBoilerDevice,
    WashcomboMainDevice,
    WashcomboMiniDevice,
    WasherDevice,
    WashtowerDevice,
    WashtowerDryerDevice,
    WashtowerWasherDevice,
    WaterHeaterDevice,
    WaterPurifierDevice,
    WineCellarDevice,
)
from thinqconnect.devices.connect_device import ConnectBaseDevice

# Common
DOMAIN = "lgthinq"
THINQ_DEFAULT_NAME: Final[str] = "LG ThinQ"
THINQ_PAT_URL: Final[str] = "https://connect-pat.lgthinq.com"

# Config Flow
CLIENT_PREFIX: Final[str] = "home-assistant"
CONF_CONNECT_CLIENT_ID: Final[str] = "connect_client_id"
DEFAULT_COUNTRY: Final[str] = "US"

# Device
DEFAULT_TEMP_STEP: int = 1
POWER_OFF: Final[str] = "POWER_OFF"
POWER_ON: Final[str] = "POWER_ON"

THINQ_DEVICE_ADDED: Final[str] = "thinq_device_added"

DEVICE_TYPE_API_MAP: Final[dict[DeviceType, ConnectBaseDevice]] = {
    DeviceType.AIR_CONDITIONER: AirConditionerDevice,
    DeviceType.AIR_PURIFIER_FAN: AirPurifierFanDevice,
    DeviceType.AIR_PURIFIER: AirPurifierDevice,
    DeviceType.CEILING_FAN: CeilingFanDevice,
    DeviceType.COOKTOP: CooktopDevice,
    DeviceType.DEHUMIDIFIER: DehumidifierDevice,
    DeviceType.DISH_WASHER: DishWasherDevice,
    DeviceType.DRYER: DryerDevice,
    DeviceType.HOME_BREW: HomeBrewDevice,
    DeviceType.HOOD: HoodDevice,
    DeviceType.HUMIDIFIER: HumidifierDevice,
    DeviceType.KIMCHI_REFRIGERATOR: KimchiRefrigeratorDevice,
    DeviceType.MICROWAVE_OVEN: MicrowaveOvenDevice,
    DeviceType.OVEN: OvenDevice,
    DeviceType.PLANT_CULTIVATOR: PlantCultivatorDevice,
    DeviceType.REFRIGERATOR: RefrigeratorDevice,
    DeviceType.ROBOT_CLEANER: RobotCleanerDevice,
    DeviceType.STICK_CLEANER: StickCleanerDevice,
    DeviceType.STYLER: StylerDevice,
    DeviceType.SYSTEM_BOILER: SystemBoilerDevice,
    DeviceType.WASHER: WasherDevice,
    DeviceType.WASHCOMBO_MAIN: WashcomboMainDevice,
    DeviceType.WASHCOMBO_MINI: WashcomboMiniDevice,
    DeviceType.WASHTOWER_DRYER: WashtowerDryerDevice,
    DeviceType.WASHTOWER: WashtowerDevice,
    DeviceType.WASHTOWER_WASHER: WashtowerWasherDevice,
    DeviceType.WATER_HEATER: WaterHeaterDevice,
    DeviceType.WATER_PURIFIER: WaterPurifierDevice,
    DeviceType.WINE_CELLAR: WineCellarDevice,
}


# Error Code
class ErrorCode(StrEnum):
    """Error codes of ThinQ Connect API."""

    INVALID_TOKEN = "1218"
    NOT_CONNECTED_DEVICE = "1222"
    NOT_ACCEPTABLE_TERMS = "1304"
    EXCEEDED_API_CALLS = "1306"
    NOT_SUPPORTED_COUNTRY = "1307"
    EXCEEDED_USER_API_CALLS = "1314"
    COMMAND_NOT_SUPPORTED_IN_STATE = "2302"
    COMMAND_NOT_SUPPORTED_IN_MODE = "2305"


# Support translation during ConfigEntry using translation_key by ErrorCode
TRANSLATION_ERROR_CODE: Final[list[str]] = [
    ErrorCode.INVALID_TOKEN,
    ErrorCode.NOT_ACCEPTABLE_TERMS,
    ErrorCode.EXCEEDED_API_CALLS,
    ErrorCode.NOT_SUPPORTED_COUNTRY,
    ErrorCode.EXCEEDED_USER_API_CALLS,
]


# Service Attributes
SERVICE_ATTR_DEVICE_INFO: Final[str] = "device_info"
SERVICE_ATTR_RESULT: Final[str] = "result"
SERVICE_ATTR_VALUE: Final[str] = "value"

# Types for profile and property.
type Profile = dict[str, Any]
type ProfileMap = dict[str, Profile]
type PropertyMap = dict[str, ProfileMap]

# Misc
NONE_KEY: Final[str] = "_"

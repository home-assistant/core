# Base component constants
import asyncio
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from ipaddress import IPv4Address
from typing import Any, Final, TypeAlias

from aiowebostv import WebOsTvCommandError
from homeassistant.config_entries import ConfigEntry
from websockets.exceptions import ConnectionClosed, ConnectionClosedOK

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
from thinqconnect.const import DeviceType
from thinqconnect.devices.connect_device import ConnectBaseDevice

DOMAIN = "lgthinq"
DATA_HASS_CONFIG = "hass_config"

#### config_flow ####
CONF_ENTRY_TYPE: Final[str] = "conf_entry_type"
CONF_ENTRY_TYPE_THINQ: Final[str] = "thinq"
CONF_ENTRY_TYPE_SOUNDBAR: Final[str] = "soundbar"
CONF_ENTRY_TYPE_WEBOSTV: Final[str] = "webostv"
CONF_SOUNDBAR_MODEL: Final[str] = "LG Soundbar Model"
DATA_CONFIG_ENTRY_WEBOSTV: Final[str] = "config_entry_webostv"
THINQ_DEFAULT_NAME: Final[str] = "LG Appliances"
SOUNDBAR_DEFAULT_NAME: Final[str] = "LG Soundbar"
WEBOS_DEFAULT_NAME = "LG webOS TV"


##### thinq #####
# Error Code
class ErrorCode(StrEnum):
    """Error code of ThinQ Connect API"""

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
    "1218",
    "1304",
    "1306",
    "1307",
    "1314",
]

# Connection information
DEFAULT_ENCODING: Final[str] = "UTF-8"
DEFAULT_COUNTRY: Final[str] = "KR"
DEFAULT_LANGUAGE: Final[str] = "ko"
CLIENT_PREFIX: Final[str] = "home-assistant"
CONF_CONNECT_CLIENT_ID: Final[str] = "connect_client_id"
CONNECT_POLLING_INTERVAL: Final[timedelta] = timedelta(seconds=1800)
MQTT_SUBSCRIPTION_INTERVAL: Final[timedelta] = timedelta(days=1)

# Device type to api map.
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

# Message Type
DEVICE_PUSH_MESSAGE: Final[str] = "DEVICE_PUSH"
DEVICE_STATUS_MESSAGE: Final[str] = "DEVICE_STATUS"
DEVICE_REGISTERED_MESSAGE: Final[str] = "DEVICE_REGISTERED"
DEVICE_UNREGISTERED_MESSAGE: Final[str] = "DEVICE_UNREGISTERED"
DEVICE_ALIAS_CHANGED_MESSAGE: Final[str] = "DEVICE_ALIAS_CHANGED"

# Service attributes
SERVICE_ATTR_DEVICE_INFO: Final[str] = "device_info"
SERVICE_ATTR_RESULT: Final[str] = "result"
SERVICE_ATTR_VALUE: Final[str] = "value"

# Signal Type
THINQ_DEVICE_ADDED: Final[str] = "thinq_device_added"

# constant
DEFAULT_TEMP_STEP: int = 1

# Common values
POWER_ON: Final[str] = "POWER_ON"
POWER_OFF: Final[str] = "POWER_OFF"

# TypeAlias
Profile: TypeAlias = dict[str, Any]
ProfileMap: TypeAlias = dict[str, Profile]
PropertyMap: TypeAlias = dict[str, ProfileMap]

##### Soundbar #####

# Connection information
SOUNDBAR_PORT: Final[int] = 9741
MANUFACTURER: Final[str] = "LG Electronics"
CONNECT_DEVICE_TIMEOUT: Final[int] = 5
CONFIG_DEVICE_TIMEOUT: Final[int] = 10

# Field List of Soundbar
SOUNDBAR_FIELD_LIST: Final[dict] = {
    "PRODUCT_INFO": [
        "s_uuid",
    ],
    "EQ_VIEW_INFO": [
        "i_bass",
        "i_treble",
        "ai_eq_list",
        "i_curr_eq",
    ],
    "SPK_LIST_VIEW_INFO": [
        # "b_powerkey",
        "b_powerstatus",
        "i_vol",
        "i_vol_min",
        "i_vol_max",
        "b_mute",
        "i_curr_func",
        "s_user_name",
    ],
    "FUNC_VIEW_INFO": [
        "i_curr_func",
        "ai_func_list",
    ],
    "SETTING_VIEW_INFO": [
        "i_rear_min",
        "i_rear_max",
        "i_rear_level",
        "i_woofer_min",
        "i_woofer_max",
        "i_woofer_level",
        "i_curr_eq",
        "s_user_name",
    ],
    "PLAY_INFO": [
        "i_stream_type",
    ],
}

##### webOS TV #####

SSDP_MX = 5
GUIDE_ENTER_TV_IP = "Please enter your webOS TV IP"
IPV4_BROADCAST = IPv4Address("255.255.255.255")
WEBOS_SECOND_SCREEN_ST = "urn:lge-com:service:webos-second-screen:1"

ATTR_BUTTON = "button"
ATTR_CONFIG_ENTRY_ID = "entry_id"
ATTR_PAYLOAD = "payload"
ATTR_SOUND_OUTPUT = "sound_output"

CONF_ON_ACTION = "turn_on_action"
CONF_SOURCES = "sources"

SERVICE_BUTTON = "button"
SERVICE_COMMAND = "command"
SERVICE_SELECT_SOUND_OUTPUT = "select_sound_output"

LIVE_TV_APP_ID = "com.webos.app.livetv"

WEBOSTV_EXCEPTIONS = (
    OSError,
    ConnectionClosed,
    ConnectionClosedOK,
    ConnectionRefusedError,
    WebOsTvCommandError,
    TimeoutError,
    asyncio.CancelledError,
)

# for entry.runtime_data
type ThinqConfigEntry = ConfigEntry[ThinqData]


@dataclass(kw_only=True)
class ThinqData:
    """Thinq data type."""

    lge_device_map: dict[str, Any]
    lge_devices: list
    lge_mqtt_clients: Any
    soundbar_client: Any

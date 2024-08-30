"""Constants for LG ThinQ."""

# Base component constants.
from typing import Final

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

# Common
DOMAIN = "lg_thinq"
COMPANY = "LGE"
THINQ_DEFAULT_NAME: Final = "LG ThinQ"
THINQ_PAT_URL: Final = "https://connect-pat.lgthinq.com"

# Config Flow
CLIENT_PREFIX: Final = "home-assistant"
CONF_CONNECT_CLIENT_ID: Final = "connect_client_id"
DEFAULT_COUNTRY: Final = "US"

THINQ_DEVICE_ADDED: Final = "thinq_device_added"

DEVICE_TYPE_API_MAP: Final = {
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

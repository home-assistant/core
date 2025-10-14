"""Constants for the Hisense AC Plugin integration."""
from typing import Final, Dict, Any, NamedTuple
from dataclasses import dataclass
from homeassistant.components.climate import ClimateEntityFeature, HVACMode
from homeassistant.components.climate.const import (
    ATTR_HVAC_MODE,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    SWING_OFF,
    SWING_VERTICAL,
    SWING_HORIZONTAL,
    SWING_BOTH,
)
from homeassistant.const import ATTR_TEMPERATURE, Platform

DOMAIN = "hisense_connectlife"
DOMAINW = "hisense_we_plugin"
STATE_HIGH_DEMANDONE = "high_demand_one"
# Custom Attributes
ATTR_INDOOR_TEMPERATURE = "indoor_temperature"
ATTR_INDOOR_HUMIDITY = "indoor_humidity"
ATTR_ENERGY_CONSUMPTION = "energy_consumption"
ATTR_QUIET_MODE = "quiet_mode"
ATTR_RAPID_MODE = "rapid_mode"
ATTR_8_DEGREE_HEAT = "eight_degree_heat"
ATTR_WATER_TANK_TEMP = "water_tank_temperature"
ATTR_ZONE_TEMPERATURE = "zone_temperature"
ATTR_AC_TYPE = "ac_type"

# # 测试环境
# OAUTH2_AUTHORIZE = "https://test-oauth.hijuconn.com/login"
# OAUTH2_TOKEN = "https://test-oauth.hijuconn.com/oauth/token"
# WEBSOCKET_URL = "wss://test-clife-eu-gateway.hijuconn.com/msg/get_msg_and_channels"
# API_BASE_URL = "https://test-juapi-3rd.hijuconn.com"

# 正式环境
OAUTH2_AUTHORIZE = "https://oauth.hijuconn.com/login"
OAUTH2_TOKEN = "https://oauth.hijuconn.com/oauth/token"
WEBSOCKET_URL = "wss://clife-eu-gateway.hijuconn.com/msg/get_msg_and_channels"
API_BASE_URL = "https://juapi-3rd.hijuconn.com"

# OAuth2 Configuration
# OAUTH2_AUTHORIZE = "https://test-oauth.hijuconn.com/login"
# OAUTH2_TOKEN = "https://test-oauth.hijuconn.com/oauth/token"

# WebSocket
# WEBSOCKET_URL = "wss://clife-eu-gateway.hijuconn.com/msg/get_msg_and_channels"
# WEBSOCKET_URL = "wss://test-clife-eu-gateway.hijuconn.com/msg/get_msg_and_channels"
WEBSOCKET_RECONNECT_INTERVAL = 30  # seconds

# API Configuration
# API_BASE_URL = "https://test-clife-eu-gateway.hijuconn.com"
# API_BASE_URL = "https://test-juapi.hijuconn.com"
# API_BASE_URL = "https://test-juapi-3rd.hijuconn.com"

API_DEVICE_LIST = "/clife-svc/pu/get_device_status_list"
API_GET_PROPERTY_LTST = "/clife-svc/get_property_list"#获取设备属性列表
API_QUERY_STATIC_DATA = "/clife-svc/pu/query_static_data"#使用puId获取设备属性列表
API_DEVICE_CONTROL = "/device/pu/property/set"
API_SELF_CHECK = "/basic/self_check/info"#获取故障信息
API_GET_HOUR_POWER = "/clife-svc/pu/get_hour_power"#获取电量信息

CLIENT_ID = "9793620883275788"
CLIENT_SECRET = "7h1m3gZVlILyBvIFBNmzXwoFYLhkGqG9NQd2jBzuZCqJKCTyCtYwQtXi4tVBjg9B"

# Token settings
TOKEN_EXPIRY_MARGIN = 60  # seconds before token expiry to refresh

# Update interval
UPDATE_INTERVAL = 30  # seconds

# Temperature settings
MIN_TEMP = 16
MAX_TEMP = 30
MIN_TEMP_WATER = 16
MAX_TEMP_WATER = 30
# Device Types
class DeviceType(NamedTuple):
    """Device type definition."""
    type_code: str
    feature_code: str
    description: str

# Known device types
DEVICE_TYPES = {
    # Split AC
    ("009", "199"): DeviceType("009", "199", "Split Air Conditioner"),
    # Window AC
    ("008", "399"): DeviceType("008", "399", "Window Air Conditioner"),
    # Add more device types here as needed
}

# Status Keys
class StatusKey:
    """Status keys for device properties."""
    POWER = "t_power"
    MODE = "t_work_mode"  # Changed from t_mode to t_work_mode
    FAN_SPEED = "t_fan_speed"
    TEMPERATURE = "f_temp_in"  # 只读温度
    T_TEMP_TYPE = "t_temp_type"  # 只读温度
    FHUMIDITY = "f_humidity"  # 只读湿度
    WATER_TANK_TEMP = "f_water_tank_temp"  # 水箱温度
    DHW_TEMP = "t_dhw_temp"  # 水箱温度
    ZONE1WATER_TEMP1 = "f_zone1water_temp1"  # 水箱温度
    ZONE1WATER_SETTEMP1 = "t_zone1water_settemp1"  # 水箱温度
    ZONE2WATER_TEMP2 = "f_zone2water_temp2"  # 水箱温度
    CONSUMPTION = "f_power_consumption"  # 耗电量
    IN_WATER_TEMP = "f_in_water_temp"  # 进水口温度
    OUT_WATER_TEMP = "f_out_water_temp"  # 出水口温度
    ELECTRIC_HEATING = "f_electric_heating"  # 电加热状态
    TARGET_TEMP = "t_temp"  # Target temperature
    HUMIDITY = "t_humidity"
    SWING = "t_up_down"  # Changed to match actual API response
    QUIET = "t_fan_mute"  # Changed to match actual API response
    RAPID = "t_super"  # Changed to match actual API response
    EIGHTHEAT = "t_8heat"  # 8°加热
    ECO = "t_eco"  # 8°加热
    EIGHT_HEAT = "t_8_heat"
    ENERGY = "f_electricity"  # Changed to match actual API response
    WATER_TEMP = "t_water_temp"
    ZONE_TEMP = "t_zone_temp"
    F_E_INTEMP = "f_e_intemp"
    F_E_INCOILTEMP = "f_e_incoiltemp"
    F_E_INHUMIDITY = "f_e_inhumidity"
    F_E_INFANMOTOR = "f_e_infanmotor"
    F_E_ARKGRILLE = "f_e_arkgrille"
    F_E_INVZERO = "f_e_invzero"
    F_E_INCOM = "f_e_incom"
    F_E_INDISPLAY = "f_e_indisplay"
    F_E_INKEYS = "f_e_inkeys"
    F_E_INWIFI = "f_e_inwifi"
    F_E_INELE = "f_e_inele"
    F_E_INEEPROM = "f_e_ineeprom"
    F_E_OUTEEPROM = "f_e_outeeprom"
    F_E_OUTCOILTEMP = "f_e_outcoiltemp"
    F_E_OUTGASTEMP = "f_e_outgastemp"
    F_E_OUTTEMP = "f_e_outtemp"
    F_E_PUSH = "f_e_push"
    F_E_WATERFULL = "f_e_waterfull"
    F_E_UPMACHINE = "f_e_upmachine"
    F_E_DWMACHINE = "f_e_dwmachine"
    F_E_FILTERCLEAN = "f_e_filterclean"
    F_E_WETSENSOR = "f_e_wetsensor"
    F_E_TUBETEMP = "f_e_tubetemp"
    F_E_TEMP = "f_e_temp"
    F_E_PUMP = "f_e_pump"
    F_E_EXHAUST_HIGHTEMP = "f_e_exhaust_hightemp"
    F_E_HIGH_PRESSURE = "f_e_high_pressure"
    F_E_LOW_PRESSURE = "f_e_low_pressure"
    F_E_WIRE_DRIVE = "f_e_wire_drive"
    F_E_COILTEMP = "f_e_coiltemp"
    F_E_ENV_TEMP = "f_e_env_temp"
    F_E_EXHAUST = "f_e_exhaust"
    F_E_INWATER = "f_e_inwater"
    F_E_WATER_TANK = "f_e_water_tank"
    F_E_RETURN_AIR = "f_e_return_air"
    F_E_OUTWATER = "f_e_outwater"
    F_E_SOLAR_TEMPERATURE = "f_e_solar_temperature"
    F_E_COMPRESSOR_OVERLOAD = "f_e_compressor_overload"
    F_E_EXCESSIVE_CURRENT = "f_e_excessive_current"
    F_E_FAN_FAULT = "f_e_fan_fault"
    F_E_DISPLAYCOM_FAULT = "f_e_displaycom_fault"
    F_E_UPWATERTANK_FAULT = "f_e_upwatertank_fault"
    F_E_DOWNWATERTANK_FAULT = "f_e_downwatertank_fault"
    F_E_SUCTIONTEMP_FAULT = "f_e_suctiontemp_fault"
    F_E_E2DATA_FAULT = "f_e_e2data_fault"
    F_E_DRIVECOM_FAULT = "f_e_drivecom_fault"
    F_E_DRIVE_FAULT = "f_e_drive_fault"
    F_E_RETURNWATERTEMP_FAULT = "f_e_returnwatertemp_fault"
    F_E_CLOCKCHIP_FAULT = "f_e_clockchip_fault"
    F_E_EANODE_FAULT = "f_e_eanode_fault"
    F_E_POWERMODULE_FAULT = "f_e_powermodule_fault"
    F_E_FAN_FAULT_TIP = "f_e_fan_fault_tip"
    F_E_PRESSURESENSOR_FAULT_TIP = "f_e_pressuresensor_fault_tip"
    F_E_TEMPFAULT_SOLARWATER_TIP = "f_e_tempfault_solarwater_tip"
    F_E_TEMPFAULT_MIXEDWATER_TIP = "f_e_tempfault_mixedwater_tip"
    F_E_TEMPFAULT_BALANCE_WATERTANK_TIP = "f_e_tempfault_balance_watertank_tip"
    F_E_TEMPFAULT_EHEATING_OUTLET_TIP = "f_e_tempfault_eheating_outlet_tip"
    F_E_TEMPFAULT_REFRIGERANT_OUTLET_TIP = "f_e_tempfault_refrigerant_outlet_tip"
    F_E_TEMPFAULT_REFRIGERANT_INLET_TIP = "f_e_tempfault_refrigerant_inlet_tip"
    F_E_INWATERPUMP_TIP = "f_e_inwaterpump_tip"
    F_E_OUTEEPROM_TIP = "f_e_outeeprom_tip"


# Operation Modes
MODE_AUTO = "auto"
MODE_COOL = "cool"
MODE_DRY = "dry"
MODE_FAN_ONLY = "fan_only"
MODE_HEAT = "heat"
MODE_ECO = "eco"
MODE_BOOST = "boost"
OPERATION_MODE_ECO  = "eco"
OPERATION_MODE_VACATION = "vacation"
# Fan Modes
FAN_AUTO = "auto"
FAN_ULTRA_LOW = "ultra_low"
SFAN_ULTRA_LOW = "中低"
FAN_LOW = "low"
FAN_MEDIUM = "medium"
FAN_HIGH = "high"
FAN_ULTRA_HIGH = "ultra_high"
SFAN_ULTRA_HIGH = "中高"

# Message Types
class MessageType:
    """Message type constants."""
    DEVICE_STATUS = "status_devicestatus"
    DEVICE_NOTIFY = "device_to_app_notify"

# AC Types
class ACType:
    """AC type constants."""
    SPLIT_AC = "split_ac"
    WINDOW_AC = "window_ac"
    PORTABLE_AC = "portable_ac"
    LIGHT_COMMERCIAL_AC = "light_commercial_ac"
    DEHUMIDIFIER = "dehumidifier"
    DUCKED_TYPE_AC = "ducked_type_ac"
    DHW = "dhw"

@dataclass
class DeviceConfiguration:
    """Device configuration class."""
    min_temp: float = DEFAULT_MIN_TEMP
    max_temp: float = DEFAULT_MAX_TEMP
    target_temp_step: float = 1.0
    fan_modes: list[str] = None
    swing_modes: list[str] = None
    features: int = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.SWING_MODE
    )
    hvac_modes: list[HVACMode] = None
    temperature_unit: str = "°C"

    def __post_init__(self):
        """Set default values for optional fields."""
        if self.fan_modes is None:
            self.fan_modes = ["auto", "high", "medium", "low"]
        if self.swing_modes is None:
            self.swing_modes = [SWING_OFF, SWING_VERTICAL]
        if self.hvac_modes is None:
            self.hvac_modes = [
                HVACMode.OFF,
                HVACMode.AUTO,
                HVACMode.COOL,
                HVACMode.DRY,
                HVACMode.FAN_ONLY,
                HVACMode.HEAT,
            ]

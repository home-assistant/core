"""Constants for Heiman integration."""

from datetime import timedelta

from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)

DOMAIN = "heiman_home"

# OAuth 2.0 配置
OAUTH_AUTHORIZE_URL = "https://spweb.heiman.cn/apploginha/sso.html"
OAUTH_TOKEN_URL = "https://spapi.heiman.cn/api-auth/oauth/token"

# API 端点
API_BASE_URL = "https://spapi.heiman.cn"

# Scopes
SCOPES = [
    # "user_info",
    # "device_list",
    # "device_control",
]

REQUESTED_SCOPES = [
    # *SCOPES,
    # "home_manage",
]

# 配置项
CONF_HOME_ID = "home_id"
CONF_USER_ID = "user_id"
CONF_REFRESH_TOKEN = "refresh_token"

# 设备过滤配置
CONF_DEVICE_FILTER = "devices_filter"
CONF_STATISTICS_LOGIC = "statistics_logic"
CONF_ROOM_FILTER_MODE = "room_filter_mode"
CONF_TYPE_FILTER_MODE = "type_filter_mode"
CONF_MODEL_FILTER_MODE = "model_filter_mode"
CONF_DEVICE_FILTER_MODE = "device_filter_mode"
CONF_ROOM_LIST = "room_list"
CONF_TYPE_LIST = "type_list"
CONF_MODEL_LIST = "model_list"
CONF_DEVICE_LIST = "device_list"

# 区域名称同步
CONF_AREA_NAME_RULE = "area_name_rule"
AREA_NAME_RULE_NONE = "none"
AREA_NAME_RULE_ROOM = "room"
AREA_NAME_RULE_HOME = "home"
AREA_NAME_RULE_HOME_ROOM = "home_room"

# 平台定义
PLATFORMS = [
    "binary_sensor",
    "sensor",
    "select",
    "switch",
    "button",
    "update",
]

# Binary Sensor 设备类映射
BINARY_SENSOR_DEVICE_CLASS_MAP = {
    "SmokeSensorState": "smoke",
    "CarbonMonoxideAlarm": "gas",
    "WaterSensorState": "moisture",
    "Contact": "door",
    "Motion": "motion",
    "TamperState": "tamper",
    "UnderVoltError": "battery",
    "FreezingPointAlarm": "cold",
    "CoStatus": "problem",
    "MotionStatus": "motion",
    "DoorStatus": "door",
}

# Sensor 设备类与单位映射
SENSOR_UNIT_MAP = {
    "temperature": {
        "device_class": "temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": "measurement",
    },
    "humidity": {
        "device_class": "humidity",
        "unit": PERCENTAGE,
        "state_class": "measurement",
    },
    "battery": {
        "device_class": "battery",
        "unit": PERCENTAGE,
        "state_class": "measurement",
    },
    "voltage": {
        "device_class": "voltage",
        "unit": UnitOfElectricPotential.VOLT,
        "state_class": "measurement",
    },
    "power": {
        "device_class": "power",
        "unit": UnitOfPower.WATT,
        "state_class": "measurement",
    },
    "energy": {
        "device_class": "energy",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "state_class": "total_increasing",
    },
    "co_concentration": {
        "device_class": "carbon_monoxide",
        "unit": CONCENTRATION_PARTS_PER_MILLION,
        "state_class": "measurement",
    },
    "signal_strength": {
        "device_class": "signal_strength",
        "unit": "dBm",
        "state_class": "measurement",
    },
}


ALARM_SOUND_OPTIONS = [
    "fast",
    "medium",
    "slow",
]

# Alarm sound display names (matching strings.json)
ALARM_SOUND_DISPLAY_NAMES = {
    "fast": "Fast Beep",
    "medium": "Medium Beep",
    "slow": "Slow Beep",
}

# 更新间隔（秒）
UPDATE_INTERVAL = timedelta(seconds=60)

# 服务定义
SERVICE_READ_DEVICE_PROPERTIES = "read_device_properties"

# 图标映射（使用 icons.json 作为主要来源，这里提供后备）
ENTITY_ICONS = {
    # Binary Sensor 图标
    "binary_sensor": {
        "SmokeSensorState": "mdi:smoke",
        "WaterSensorState": "mdi:water",
        "TamperState": "mdi:alert",
        "UnderVoltError": "mdi:battery-alert-variant",
        "FreezingPointAlarm": "mdi:water-thermometer-outline",
        "MotionStatus": "mdi:motion-sensor",
        "DoorStatus": "mdi:door",
        "CoStatus": "mdi:molecule-co",
    },
    # Sensor 图标
    "sensor": {
        "CurrentTemperature": "mdi:thermometer",
        "BatteryPercentage": "mdi:battery",
        "DeviceINFO_DBM": "mdi:signal",
        "DeviceINFO_DBM_Level": "mdi:signal",
        "DeviceINFO_MAC": "mdi:dharmachakra",
        "DeviceINFO_IP": "mdi:ip",
        "DeviceMac": "mdi:dharmachakra",
        "humidity": "mdi:water-percent",
        "temperature": "mdi:thermometer",
        "SignalStrength": "mdi:signal",
        "TimeZone": "mdi:clock-time-nine-outline",
    },
    # Switch 图标
    "switch": {
        "LightSwitch": "mdi:lightbulb-outline",
        "FreezingPointEnable": "mdi:snowflake-alert",
        "BuzzerEnable": "mdi:surround-sound",
    },
    # Button 图标
    "button": {
        "RemoteLocate": "mdi:radar",
        "RemoteCheck": "mdi:clipboard-check",
        "Mute": "mdi:volume-mute",
    },
    # Select 图标
    "select": {"AlarmSoundOption": "mdi:volume-high"},
}

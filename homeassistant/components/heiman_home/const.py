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

# OAuth 2.0 Configuration
OAUTH_AUTHORIZE_URL = "https://spapi.heiman.cn/api-auth/system/auth/ha/oauth/authorize"
OAUTH_TOKEN_URL = "https://spapi.heiman.cn/api-auth/oauth/token"

# API Endpoint
API_BASE_URL = "https://spapi.heiman.cn"

# Scopes
SCOPES: list[str] = [
    # "user_info",
    # "device_list",
    # "device_control",
]

REQUESTED_SCOPES: list[str] = [
    # *SCOPES,
    # "home_manage",
]

# Configuration Items
CONF_HOME_ID = "home_id"
CONF_USER_ID = "user_id"
CONF_REFRESH_TOKEN = "refresh_token"

# Device Filter Configuration
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

# Area Name Sync
CONF_AREA_NAME_RULE = "area_name_rule"
AREA_NAME_RULE_NONE = "none"
AREA_NAME_RULE_ROOM = "room"
AREA_NAME_RULE_HOME = "home"
AREA_NAME_RULE_HOME_ROOM = "home_room"

# Platform Definitions
PLATFORMS = [
    # "binary_sensor",
    "sensor",
    # "select",
    # "switch",
    # "button",
    # "update",
]

# Binary Sensor Device Class Mapping
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

# Sensor Device Class and Unit Mapping
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

# Update Interval (seconds)
UPDATE_INTERVAL = timedelta(seconds=60)

# Service Definitions
SERVICE_READ_DEVICE_PROPERTIES = "read_device_properties"

# Icon Mapping (icons.json is primary source, this provides fallback)
ENTITY_ICONS = {
    # Binary Sensor Icons
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
    # Sensor Icons
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
    # Switch Icons
    "switch": {
        "LightSwitch": "mdi:lightbulb-outline",
        "FreezingPointEnable": "mdi:snowflake-alert",
        "BuzzerEnable": "mdi:surround-sound",
    },
    # Button Icons
    "button": {
        "RemoteLocate": "mdi:radar",
        "RemoteCheck": "mdi:clipboard-check",
        "Mute": "mdi:volume-mute",
    },
    # Select Icons
    "select": {"AlarmSoundOption": "mdi:volume-high"},
}

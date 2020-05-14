"""MySensors constants."""
from collections import defaultdict

ATTR_DEVICES = "devices"

CONF_BAUD_RATE = "baud_rate"
CONF_DEVICE = "device"
CONF_GATEWAYS = "gateways"
CONF_NODES = "nodes"
CONF_PERSISTENCE = "persistence"
CONF_PERSISTENCE_FILE = "persistence_file"
CONF_RETAIN = "retain"
CONF_TCP_PORT = "tcp_port"
CONF_TOPIC_IN_PREFIX = "topic_in_prefix"
CONF_TOPIC_OUT_PREFIX = "topic_out_prefix"
CONF_VERSION = "version"

DOMAIN = "mysensors"
MYSENSORS_GATEWAY_READY = "mysensors_gateway_ready_{}"
MYSENSORS_GATEWAYS = "mysensors_gateways"
PLATFORM = "platform"
SCHEMA = "schema"
CHILD_CALLBACK = "mysensors_child_callback_{}_{}_{}_{}"
NODE_CALLBACK = "mysensors_node_callback_{}_{}"
TYPE = "type"
UPDATE_DELAY = 0.1

SERVICE_SEND_IR_CODE = "send_ir_code"

BINARY_SENSOR_TYPES = {
    "S_DOOR": {"V_TRIPPED"},
    "S_MOTION": {"V_TRIPPED"},
    "S_SMOKE": {"V_TRIPPED"},
    "S_SPRINKLER": {"V_TRIPPED"},
    "S_WATER_LEAK": {"V_TRIPPED"},
    "S_SOUND": {"V_TRIPPED"},
    "S_VIBRATION": {"V_TRIPPED"},
    "S_MOISTURE": {"V_TRIPPED"},
}

CLIMATE_TYPES = {"S_HVAC": {"V_HVAC_FLOW_STATE"}}

COVER_TYPES = {"S_COVER": {"V_DIMMER", "V_PERCENTAGE", "V_LIGHT", "V_STATUS"}}

DEVICE_TRACKER_TYPES = {"S_GPS": {"V_POSITION"}}

LIGHT_TYPES = {
    "S_DIMMER": {"V_DIMMER", "V_PERCENTAGE"},
    "S_RGB_LIGHT": {"V_RGB"},
    "S_RGBW_LIGHT": {"V_RGBW"},
}

NOTIFY_TYPES = {"S_INFO": {"V_TEXT"}}

SENSOR_TYPES = {
    "S_SOUND": {"V_LEVEL"},
    "S_VIBRATION": {"V_LEVEL"},
    "S_MOISTURE": {"V_LEVEL"},
    "S_INFO": {"V_TEXT"},
    "S_GPS": {"V_POSITION"},
    "S_TEMP": {"V_TEMP"},
    "S_HUM": {"V_HUM"},
    "S_BARO": {"V_PRESSURE", "V_FORECAST"},
    "S_WIND": {"V_WIND", "V_GUST", "V_DIRECTION"},
    "S_RAIN": {"V_RAIN", "V_RAINRATE"},
    "S_UV": {"V_UV"},
    "S_WEIGHT": {"V_WEIGHT", "V_IMPEDANCE"},
    "S_POWER": {"V_WATT", "V_KWH", "V_VAR", "V_VA", "V_POWER_FACTOR"},
    "S_DISTANCE": {"V_DISTANCE"},
    "S_LIGHT_LEVEL": {"V_LIGHT_LEVEL", "V_LEVEL"},
    "S_IR": {"V_IR_RECEIVE"},
    "S_WATER": {"V_FLOW", "V_VOLUME"},
    "S_CUSTOM": {"V_VAR1", "V_VAR2", "V_VAR3", "V_VAR4", "V_VAR5", "V_CUSTOM"},
    "S_SCENE_CONTROLLER": {"V_SCENE_ON", "V_SCENE_OFF"},
    "S_COLOR_SENSOR": {"V_RGB"},
    "S_MULTIMETER": {"V_VOLTAGE", "V_CURRENT", "V_IMPEDANCE"},
    "S_GAS": {"V_FLOW", "V_VOLUME"},
    "S_WATER_QUALITY": {"V_TEMP", "V_PH", "V_ORP", "V_EC"},
    "S_AIR_QUALITY": {"V_DUST_LEVEL", "V_LEVEL"},
    "S_DUST": {"V_DUST_LEVEL", "V_LEVEL"},
}

SWITCH_TYPES = {
    "S_LIGHT": {"V_LIGHT"},
    "S_BINARY": {"V_STATUS"},
    "S_DOOR": {"V_ARMED"},
    "S_MOTION": {"V_ARMED"},
    "S_SMOKE": {"V_ARMED"},
    "S_SPRINKLER": {"V_STATUS"},
    "S_WATER_LEAK": {"V_ARMED"},
    "S_SOUND": {"V_ARMED"},
    "S_VIBRATION": {"V_ARMED"},
    "S_MOISTURE": {"V_ARMED"},
    "S_IR": {"V_IR_SEND"},
    "S_LOCK": {"V_LOCK_STATUS"},
    "S_WATER_QUALITY": {"V_STATUS"},
}


PLATFORM_TYPES = {
    "binary_sensor": BINARY_SENSOR_TYPES,
    "climate": CLIMATE_TYPES,
    "cover": COVER_TYPES,
    "device_tracker": DEVICE_TRACKER_TYPES,
    "light": LIGHT_TYPES,
    "notify": NOTIFY_TYPES,
    "sensor": SENSOR_TYPES,
    "switch": SWITCH_TYPES,
}

FLAT_PLATFORM_TYPES = {
    (platform, s_type_name): v_type_name
    for platform, platform_types in PLATFORM_TYPES.items()
    for s_type_name, v_type_name in platform_types.items()
}

TYPE_TO_PLATFORMS = defaultdict(list)
for platform, platform_types in PLATFORM_TYPES.items():
    for s_type_name in platform_types:
        TYPE_TO_PLATFORMS[s_type_name].append(platform)

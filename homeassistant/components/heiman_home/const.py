"""Constants for Heiman Home Integration."""

# Domain name
DOMAIN = "heiman_home"

# Integration name
NAME = "Heiman Home"

# Version
VERSION = "0.1.0"

# Supported platforms
PLATFORMS = [
    "sensor",
    "binary_sensor",
    "switch",
    "climate",
    "button",
    "cover",
    "device_tracker",
    "event",
    "fan",
    "humidifier",
    "light",
    "media_player",
    "number",
    "select",
    "text",
    "update",
]

# Cloud API endpoints
API_BASE_URL_CN = "https://api.heiman.cn"
API_BASE_URL_EU = "https://spapi.heiman.cn"
API_BASE_URL_TEST = "http://192.168.1.14:9900"

# MQTT endpoints
MQTT_BROKER_CN = "mqtt.heiman.cn"
MQTT_BROKER_EU = "spmqtt.heiman.cn"
MQTT_BROKER_TEST = "192.168.1.14"

# MQTT ports
MQTT_PORT_TCP = 1883
MQTT_PORT_SSL = 1884

# Configuration keys
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_API_URL = "api_url"
CONF_MQTT_BROKER = "mqtt_broker"
CONF_HOME_ID = "home_id"
CONF_HOME_IDS = "home_ids"
CONF_REGION = "region"
CONF_SECURE_ID = "secure_id"
CONF_SECURE_KEY = "secure_key"
CONF_USER_ID = "user_id"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_TOKEN_EXPIRES_TS = "token_expires_ts"
CONF_INTEGRATION_LANGUAGE = "integration_language"

# Default values
DEFAULT_REGION = "eu"
DEFAULT_SCAN_INTERVAL = 300  # Increased to 5 minutes to reduce API load
DEFAULT_HTTP_TIMEOUT = 30

# Regions - Only EU is enabled by default, CN and TEST are commented out
REGIONS = {
    # "cn": {
    #     "api_url": API_BASE_URL_CN,
    #     "mqtt_broker": MQTT_BROKER_CN,
    #     "oauth_auth_url": "https://web.heiman.cn/apploginha/sso.html",
    #     "oauth_token_url": "https://api.heiman.cn/api-auth/oauth/token",
    #     "oauth_userinfo_url": "https://api.heiman.cn/api-app/appUser/get/info",
    # },
    "eu": {
        "api_url": API_BASE_URL_EU,
        "mqtt_broker": MQTT_BROKER_EU,
        "oauth_auth_url": "https://spweb.heiman.cn/apploginha/sso.html",
        "oauth_token_url": "https://spapi.heiman.cn/api-auth/oauth/token",
        "oauth_userinfo_url": "https://spapi.heiman.cn/api-app/appUser/get/info",
    },
    # "test": {
    #     "api_url": API_BASE_URL_TEST,
    #     "mqtt_broker": MQTT_BROKER_TEST,
    #     "oauth_auth_url": "http://192.168.1.14:5374/sso.html",
    #     "oauth_token_url": "http://192.168.1.14:9900/api-auth/oauth/token",
    #     "oauth_userinfo_url": "http://192.168.1.14:9900/api-app/appUser/get/info",
    # }
}

# API endpoints
API_ENDPOINTS = {
    "login": "/api-app/login",
    "get_homes": "/api-app/homeUserRelation/get/homeList",
    "get_devices": "/api-app/device/get/listByHomeId",
    "get_device_info": "/api-app/device/get/info",
}

# OAuth2 Configuration
OAUTH2_CLIENT_ID = "htJXYn5TyM3zZ7ji"
OAUTH2_CLIENT_SECRET = "htJXYn5TyM3zZ7ji"
OAUTH2_AUTH_URL = "http://192.168.1.14:5374/sso.html"
OAUTH2_TOKEN_URL = "http://192.168.1.14:9900/api-auth/oauth/token"
OAUTH2_USERINFO_URL = "http://192.168.1.14:9900/api-app/appUser/get/info"
OAUTH2_REDIRECT_URL = "http://localhost:8123"
# OAUTH2_REDIRECT_URL = "http://homeassistant.local:8123"

# Default OAuth2 configuration
DEFAULT_CLOUD_SERVER = "cn"
DEFAULT_SECURE_ID = "htJXYn5TyM3zZ7ji"
DEFAULT_SECURE_KEY = "htJXYn5TyM3zZ7ji"

# MQTT topics
MQTT_TOPIC_PROPERTIES_READ = "/{product_id}/{device_id}/properties/read"
MQTT_TOPIC_PROPERTIES_WRITE = "/{product_id}/{device_id}/properties/write"
MQTT_TOPIC_PROPERTIES_REPORT = "/{product_id}/{device_id}/properties/report"
MQTT_TOPIC_PROPERTIES_READ_REPLY = "/{product_id}/{device_id}/properties/read/reply"
MQTT_TOPIC_PROPERTIES_WRITE_REPLY = "/{product_id}/{device_id}/properties/write/reply"

# Secure credentials (fixed values)
SECURE_ID = "htJXYn5TyM3zZ7ji"
SECURE_KEY = "htJXYn5TyM3zZ7ji"

# Authentication types
AUTH_TYPE_DEVICE = "device"
AUTH_TYPE_USER = "user"
AUTH_TYPE_APP = "app"

# Device types
DEVICE_TYPE_GATEWAY = "gateway"
DEVICE_TYPE_SENSOR = "sensor"
DEVICE_TYPE_SWITCH = "switch"
DEVICE_TYPE_CONTROLLER = "controller"

# Integration language support
DEFAULT_INTEGRATION_LANGUAGE = "zh-Hans"
INTEGRATION_LANGUAGES = {
    "de": "Deutsch",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "it": "Italiano",
    "ja": "日本語",
    "nl": "Nederlands",
    "pt": "Português",
    "pt-BR": "Português (Brasil)",
    "ru": "Русский",
    "tr": "Türkçe",
    "zh-Hans": "简体中文",
    "zh-Hant": "繁體中文",
}

# Device filter mode
FILTER_MODE_INCLUDE = "include"
FILTER_MODE_EXCLUDE = "exclude"

# Room name sync modes (same as xiaomi_home)
AREA_NAME_RULE_NONE = "none"
AREA_NAME_RULE_ROOM = "room"
AREA_NAME_RULE_HOME = "home"
AREA_NAME_RULE_HOME_ROOM = "home_room"

AREA_NAME_RULES = {
    AREA_NAME_RULE_NONE: "不同步",
    AREA_NAME_RULE_ROOM: "房间名",
    AREA_NAME_RULE_HOME: "家庭名",
    AREA_NAME_RULE_HOME_ROOM: "家庭名 和 房间名",
}

# Update interval
SCAN_INTERVAL = 30  # seconds

# Config keys for area name rule
CONF_AREA_NAME_RULE = "area_name_rule"
CONF_DEVICES_CONFIG = "devices_config"

# Device management configuration keys
CONF_DEVICE_FILTER = "devices_filter"
CONF_HIDE_NON_STANDARD = "hide_non_standard_entities"
CONF_ACTION_DEBUG = "action_debug_mode"
CONF_BINARY_SENSOR_DISPLAY_MODE = "binary_sensor_display_mode"
CONF_DISPLAY_DEVICES_CHANGED_NOTIFY = "display_devices_changed_notify"
CONF_STATISTICS_LOGIC = "statistics_logic"
CONF_ROOM_FILTER_MODE = "room_filter_mode"
CONF_TYPE_FILTER_MODE = "type_filter_mode"
CONF_MODEL_FILTER_MODE = "model_filter_mode"
CONF_DEVICE_FILTER_MODE = "device_filter_mode"
CONF_ROOM_LIST = "room_list"
CONF_TYPE_LIST = "type_list"
CONF_MODEL_LIST = "model_list"
CONF_DEVICE_LIST = "device_list"

# Service names
SERVICE_SYNC_CHILD_DEVICES = "sync_child_devices"

# Service attributes
ATTR_GATEWAY_DEVICE_ID = "gateway_device_id"

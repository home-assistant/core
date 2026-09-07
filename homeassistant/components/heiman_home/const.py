"""Constants for Heiman integration."""

DOMAIN = "heiman_home"

# OAuth 2.0 Configuration
OAUTH_AUTHORIZE_URL = "https://spapi.heiman.cn/api-auth/system/auth/ha/oauth/authorize"
OAUTH_TOKEN_URL = "https://spapi.heiman.cn/api-auth/oauth/token"

# API Endpoint
API_BASE_URL = "https://spapi.heiman.cn"

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
PLATFORMS = ["sensor"]

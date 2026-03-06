"""Constants."""

from homeassistant.const import Platform

DOMAIN = "imou"

# API URL region mapping
API_URLS: dict[str, str] = {
    "sg": "openapi-sg.easy4ip.com",
    "eu": "openapi-or.easy4ip.com",
    "na": "openapi-fk.easy4ip.com",
    "cn": "openapi.lechange.cn",
}

CONF_API_URL = "api_url"
CONF_APP_ID = "app_id"
CONF_APP_SECRET = "app_secret"

PARAM_STATUS = "status"
PARAM_STATE = "state"

# Button types
PARAM_RESTART_DEVICE = "restart_device"
PARAM_MUTE = "mute"
PARAM_PTZ_UP = "ptz_up"
PARAM_PTZ_DOWN = "ptz_down"
PARAM_PTZ_LEFT = "ptz_left"
PARAM_PTZ_RIGHT = "ptz_right"

BUTTON_TYPES = (
    PARAM_RESTART_DEVICE,
    PARAM_MUTE,
    PARAM_PTZ_UP,
    PARAM_PTZ_DOWN,
    PARAM_PTZ_LEFT,
    PARAM_PTZ_RIGHT,
)

PLATFORMS = [Platform.BUTTON]

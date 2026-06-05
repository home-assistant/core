"""Constants."""

from pyimouapi.ha_device import ImouHaDevice

from homeassistant.const import Platform

DOMAIN = "imou"


def imou_device_identifier(device: ImouHaDevice) -> str:
    """Return a device registry identifier (device_id + channel when present)."""
    if device.channel_id is not None:
        return f"{device.device_id}_{device.channel_id}"
    return device.device_id


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
PARAM_HEADER_DETECT = "header_detect"

CONF_OPTION_LIVE_RESOLUTION = "live_resolution"
CONF_OPTION_UPDATE_INTERVAL = "update_interval"
# Config entry option values (selector keys; must be [a-z0-9-_]+ for translations).
LIVE_RESOLUTION_HD = "hd"
LIVE_RESOLUTION_SD = "sd"
DEFAULT_LIVE_RESOLUTION = LIVE_RESOLUTION_SD
# pyimouapi async_get_device_stream resolution argument values.
PYIMOUAPI_LIVE_RESOLUTIONS: dict[str, str] = {
    LIVE_RESOLUTION_HD: "HD",
    LIVE_RESOLUTION_SD: "SD",
}
MIN_UPDATE_INTERVAL_SECONDS = 30
MAX_UPDATE_INTERVAL_SECONDS = 900
DEFAULT_UPDATE_INTERVAL_SECONDS = 120

# How long each PTZ button press moves the camera, in milliseconds (Imou cloud API).
PTZ_MOVE_DURATION_MS = 500

# Upper bound for a full coordinator refresh (device list + status for all devices).
UPDATE_TIMEOUT = 300

PLATFORMS = [Platform.BUTTON, Platform.CAMERA]

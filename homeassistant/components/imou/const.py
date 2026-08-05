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
PARAM_MOTION_DETECT = "motion_detect"
PARAM_HEADER_DETECT = "header_detect"
PARAM_WHITE_LIGHT = "white_light"
PARAM_CLOSE_CAMERA = "close_camera"
PARAM_AB_ALARM_SOUND = "ab_alarm_sound"
PARAM_AUDIO_ENCODE_CONTROL = "audio_encode_control"
PARAM_LIGHT = "light"
PARAM_PLUG_SWITCH = "switch"

# How long each PTZ button press moves the camera, in milliseconds (Imou cloud API).
PTZ_MOVE_DURATION_MS = 500

# Upper bound for a full coordinator refresh (device list + status for all devices).
UPDATE_TIMEOUT = 300

PLATFORMS = [Platform.BUTTON, Platform.CAMERA, Platform.SENSOR, Platform.SWITCH]

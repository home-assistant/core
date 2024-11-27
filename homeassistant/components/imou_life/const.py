"""Constants."""
# Internal constants
DOMAIN = "imou_life"

# Configuration definitions
CONF_API_URL_SG = "openapi-sg.easy4ip.com"
CONF_API_URL_OR = "openapi-or.easy4ip.com"
CONF_API_URL_FK = "openapi-fk.easy4ip.com"
CONF_CLOSE_CAMERA = "CloseCamera"
CONF_WHITE_LIGHT = "WhiteLight"
CONF_AB_ALARM_SOUND = "AbAlarmSound"
CONF_AUDIO_ENCODE_CONTROL = "AudioEncodeControl"
CONF_NVM = "NVM"
CONF_PT = "PT"

# parameters:
PARAM_API_URL = "api_url"
PARAM_APP_ID = "app_id"
PARAM_APP_SECRET = "app_secret"
PARAM_MOTION_DETECT = "motion_detect"
PARAM_MOBILE_DETECT = "mobile_detect"
PARAM_STATUS = "status"
PARAM_STORAGE_USED = "storage_used"
PARAM_NIGHT_VISION_MODE = "night_vision_mode"
PARAM_MODE = "mode"
PARAM_CURRENT_OPTION = "current_option"
PARAM_MODES = "modes"
PARAM_OPTIONS = "options"
PARAM_CHANNELS = "channels"
PARAM_CHANNEL_ID = "channelId"
PARAM_USED_BYTES = "usedBytes"
PARAM_TOTAL_BYTES = "totalBytes"
PARAM_STREAMS = "streams"
PARAM_HLS = "hls"
PARAM_RESTART_DEVICE = "restart_device"
PARAM_URL = "url"
PARAM_PROPERTIES = "properties"
PARAM_CLOSE_CAMERA = "close_camera"
PARAM_WHITE_LIGHT = "white_light"
PARAM_AB_ALARM_SOUND = "ab_alarm_sound"
PARAM_AUDIO_ENCODE_CONTROL = "audio_encode_control"
PARAM_STREAM_ID = "streamId"

PLATFORMS = [
    "select",
    "sensor",
    "switch",
    "camera",
    "button"
]

SWITCH_TYPE_ABILITY = {
    "close_camera": "CloseCamera",
    "white_light": "WhiteLight",
    "audio_encode_control": "AudioEncodeControl",
    "ab_alarm_sound": "AbAlarmSound"
}

SWITCH_TYPE_ENABLE = {
    "motion_detect": ["motionDetect", "mobileDetect"],
    "close_camera": ["closeCamera"],
    "white_light": ["whiteLight"],
    "audio_encode_control": ["audioEncodeControl"],
    "ab_alarm_sound": ["abAlarmSound"]
}

BUTTON_TYPE_PARAM_VALUE = {
    "ptz_up": 0,
    "ptz_down": 1,
    "ptz_left": 2,
    "ptz_right": 3
}

"""Constants for the Onkyo integration."""

DOMAIN = "onkyo"
BRAND_NAME = "Onkyo"

EISCP_IDENTIFIER = "identifier"
EISCP_MODEL_NAME = "model_name"

CONF_DEVICE = "device"
CONF_MAXIMUM_VOLUME = "maximum_volume"
CONF_MAXIMUM_VOLUME_DEFAULT = 100
CONF_RECEIVER_MAXIMUM_VOLUME = "receiver_max_volume"
CONF_RECEIVER_MAXIMUM_VOLUME_DEFAULT = 80
CONF_SOURCES = "sources"
CONF_SOURCES_DEFAULT = {
    "tv": "TV",
    "bd": "Bluray",
    "game": "Game",
    "aux1": "Aux1",
    "video1": "Video 1",
    "video2": "Video 2",
    "video3": "Video 3",
    "video4": "Video 4",
    "video5": "Video 5",
    "video6": "Video 6",
    "video7": "Video 7",
    "fm": "Radio",
}
CONF_EISCP = "eiscp"
CONF_EISCP_DEFAULT = {
    "audyssey-dynamic-volume": [
        "off",
        "light",
        "medium",
        "heavy",
    ]
}

ATTR_AUDIO_INFORMATION = "audio_information"
ATTR_HDMI_OUTPUT = "hdmi_output"
ATTR_PRESET = "preset"
ATTR_VIDEO_INFORMATION = "video_information"
ATTR_VIDEO_OUT = "video_out"

DEFAULT_PLAYABLE_SOURCES = ("fm", "am", "tuner")

TIMEOUT_MESSAGE = "Timeout waiting for response."

SERVICE_SELECT_HDMI_OUTPUT = "onkyo_select_hdmi_output"
HDMI_OUTPUT_ACCEPTED_VALUES = [
    "no",
    "analog",
    "yes",
    "out",
    "out-sub",
    "sub",
    "hdbaset",
    "both",
    "up",
]

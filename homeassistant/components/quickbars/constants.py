"""Constants for the QuickBars integration."""

# Attribute keys used by services/actions
ATTR_ALIAS = "alias"
ATTR_DEVICE_ID = "device_id"

ATTR_CAMERA_ALIAS = "camera_alias"
ATTR_CAMERA_ENTITY = "camera_entity"
ATTR_RTSP_URL = "rtsp_url"
ATTR_POSITION = "position"
ATTR_SIZE = "size"
ATTR_SIZE_PX = "size_px"
ATTR_WIDTH = "w"
ATTR_HEIGHT = "h"
ATTR_AUTO_HIDE = "auto_hide"
ATTR_SHOW_TITLE = "show_title"


SIZE_CHOICES = ["small", "medium", "large"]


ALLOWED_DOMAINS = [
    "light",
    "switch",
    "button",
    "fan",
    "input_boolean",
    "input_button",
    "script",
    "scene",
    "climate",
    "cover",
    "sensor",
    "binary_sensor",
    "lock",
    "alarm_control_panel",
    "camera",
    "automation",
    "media_player",
]
DOMAIN = "quickbars"

EVENT_NAME = "quickbars.open"
SERVICE_TYPE = "_quickbars._tcp.local."

# camera positions
POS_CHOICES = ["top_left", "top_right", "bottom_left", "bottom_right"]

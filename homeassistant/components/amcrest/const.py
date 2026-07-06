"""Constants for amcrest component."""

DOMAIN = "amcrest"
DATA_AMCREST = DOMAIN
DEVICES = "devices"

BINARY_SENSOR_SCAN_INTERVAL_SECS = 5
CAMERA_WEB_SESSION_TIMEOUT = 10
COMM_RETRIES = 1
COMM_TIMEOUT = 6.05
SENSOR_SCAN_INTERVAL_SECS = 10
SNAPSHOT_TIMEOUT = 20

SERVICE_EVENT = "event"
SERVICE_UPDATE = "update"

RESOLUTION_LIST = {"high": 0, "low": 1}
RESOLUTION_TO_STREAM = {0: "Main", 1: "Extra"}

ATTR_COLOR_BW = "color_bw"
CBW = ["color", "auto", "bw"]
MOV = [
    "zoom_out",
    "zoom_in",
    "right",
    "left",
    "up",
    "down",
    "right_down",
    "right_up",
    "left_down",
    "left_up",
]

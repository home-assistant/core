"""Constants for amcrest component."""
DOMAIN = "amcrest"
CAMERAS = "cameras"
DEVICES = "devices"

DEFAULT_NAME = "Amcrest Camera"
DEFAULT_PORT = 80
DEFAULT_RESOLUTION = "high"
DEFAULT_STREAM_SOURCE = "snapshot"
DEFAULT_FFMPEG_ARGUMENTS = "-pred 1"
DEFAULT_CONTROL_LIGHT = False
DEFAULT_AUTHENTICATION = "basic"

CONF_RESOLUTION = "resolution"
CONF_STREAM_SOURCE = "stream_source"
CONF_FFMPEG_ARGUMENTS = "ffmpeg_arguments"
CONF_CONTROL_LIGHT = "control_light"

RESOLUTION_LIST = ["high", "low"]
AUTHENTICATION_LIST = {"basic": "basic"}
STREAM_SOURCE_LIST = ["snapshot", "mjpeg", "rtsp"]

BINARY_SENSOR_SCAN_INTERVAL_SECS = 5
CAMERA_WEB_SESSION_TIMEOUT = 10
COMM_RETRIES = 1
COMM_TIMEOUT = 6.05
SENSOR_SCAN_INTERVAL_SECS = 10
SNAPSHOT_TIMEOUT = 20

SERVICE_EVENT = "event"
SERVICE_UPDATE = "update"

RESOLUTION_TO_STREAM = {"high": "Main", "low": "Extra"}

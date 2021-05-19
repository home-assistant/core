"""Constants for the motionEye integration."""
from datetime import timedelta

DOMAIN = "motioneye"

CONF_CLIENT = "client"
CONF_COORDINATOR = "coordinator"
CONF_ADMIN_PASSWORD = "admin_password"
CONF_ADMIN_USERNAME = "admin_username"
CONF_SURVEILLANCE_USERNAME = "surveillance_username"
CONF_SURVEILLANCE_PASSWORD = "surveillance_password"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

MOTIONEYE_MANUFACTURER = "motionEye"

SIGNAL_CAMERA_ADD = f"{DOMAIN}_camera_add_signal." "{}"
SIGNAL_CAMERA_REMOVE = f"{DOMAIN}_camera_remove_signal." "{}"

TYPE_MOTIONEYE_MJPEG_CAMERA = "motioneye_mjpeg_camera"

"""Constants for the motionEye integration."""
from datetime import timedelta

CONF_CLIENT = "client"
CONF_COORDINATOR = "coordinator"
CONF_ON_UNLOAD = "on_unload"
CONF_ADMIN_PASSWORD = "admin_password"
CONF_ADMIN_USERNAME = "admin_username"
CONF_SURVEILLANCE_USERNAME = "surveillance_username"
CONF_SURVEILLANCE_PASSWORD = "surveillance_password"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
DOMAIN = "motioneye"

MOTIONEYE_MANUFACTURER = "motionEye"

SIGNAL_ENTITY_REMOVE = f"{DOMAIN}_entity_remove_signal." "{}"

TYPE_MOTIONEYE_MJPEG_CAMERA = "motioneye_mjpeg_camera"

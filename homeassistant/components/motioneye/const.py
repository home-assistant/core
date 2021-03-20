"""Constants for the motionEye integration."""
from datetime import timedelta

CONF_CLIENT = "client"
CONF_COORDINATOR = "coordinator"
CONF_ON_UNLOAD = "on_unload"
CONF_PASSWORD_ADMIN = "password_admin"
CONF_PASSWORD_SURVEILLANCE = "password_surveillance"
CONF_USERNAME_ADMIN = "username_admin"
CONF_USERNAME_SURVEILLANCE = "username_surveillance"
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)
DOMAIN = "motioneye"

SIGNAL_ENTITY_REMOVE = f"{DOMAIN}_entity_remove_signal." "{}"

TYPE_MOTIONEYE_MJPEG_CAMERA = "motioneye_mjpeg_camera"

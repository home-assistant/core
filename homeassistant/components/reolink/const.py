"""Constants for the Reolink Camera integration."""

DOMAIN = "reolink"
PLATFORMS = ["camera"]

CONF_USE_HTTPS = "use_https"
CONF_PROTOCOL = "protocol"

DEFAULT_PROTOCOL = "rtsp"
DEFAULT_TIMEOUT = 60

HOST = "host"
DEVICE_CONFIG_UPDATE_COORDINATOR = "coordinator"
DEVICE_UPDATE_INTERVAL = 60

SUPPORT_PTZ = 1024

SERVICE_PTZ_CONTROL = "ptz_control"
SERVICE_SET_BACKLIGHT = "set_backlight"
SERVICE_SET_DAYNIGHT = "set_daynight"
SERVICE_SET_SENSITIVITY = "set_sensitivity"

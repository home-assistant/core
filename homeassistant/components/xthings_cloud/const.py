"""Constants for Xthings Cloud integration."""

import logging

DOMAIN = "xthings_cloud"
LOGGER = logging.getLogger(__package__)

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_TOKEN = "token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_CLIENT_ID = "client_id"
CONF_INSTANCE_ID = "instance_id"
CONF_REMOTE_ACCESS = "remote_access"

# API endpoints
API_BASE_URL = "https://api.cloud.xthings.com/ha"
API_LOGIN_URL = f"{API_BASE_URL}/auth/login"
API_DEVICES_URL = f"{API_BASE_URL}/device"
API_DEVICE_STATUS_URL = f"{API_BASE_URL}/device/status"
API_REFRESH_TOKEN_URL = f"{API_BASE_URL}/auth/refresh"
API_CAMERA_WEBRTC_URL = f"{API_BASE_URL}/device/camera/command/webrtc"

# Brite (light) control endpoints
API_BRITE_ON_URL = f"{API_BASE_URL}/device/brite/command/on"
API_BRITE_OFF_URL = f"{API_BASE_URL}/device/brite/command/off"
API_BRITE_BRIGHTNESS_URL = f"{API_BASE_URL}/device/brite/command/brightness"
API_BRITE_COLOR_URL = f"{API_BASE_URL}/device/brite/command/color"

# Switch control endpoints
API_SWITCH_ON_URL = f"{API_BASE_URL}/device/switch/command/on"
API_SWITCH_OFF_URL = f"{API_BASE_URL}/device/switch/command/off"
API_SWITCH_BRIGHTNESS_URL = f"{API_BASE_URL}/device/switch/command/brightness"

# Lock control endpoints
API_LOCK_LOCK_URL = f"{API_BASE_URL}/device/lock/command/lock"
API_LOCK_UNLOCK_URL = f"{API_BASE_URL}/device/lock/command/unlock"

# Plug control endpoints
API_PLUG_ON_URL = f"{API_BASE_URL}/device/plug/command/on"
API_PLUG_OFF_URL = f"{API_BASE_URL}/device/plug/command/off"

# FRP remote access endpoint
API_FRP_HTTP_URL = f"{API_BASE_URL}/frp/get/http"

# FRP S3 download base URL
FRP_S3_BASE_URL = "https://xthings-deploy-package.s3.us-west-2.amazonaws.com/Frp"

# WebSocket
WS_URL = "wss://api.cloud.xthings.com/api/ws"

# Polling interval (seconds)
DEFAULT_SCAN_INTERVAL = 1800

PLATFORMS: list[str] = ["switch", "light", "lock", "camera", "sensor"]

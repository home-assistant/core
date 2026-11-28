"""Go2rtc constants."""

DOMAIN = "go2rtc"

CONF_DEBUG_UI = "debug_ui"
DEBUG_UI_URL_MESSAGE = "Url and debug_ui cannot be set at the same time."
HA_MANAGED_API_PORT = 11984
HA_MANAGED_URL = f"http://localhost:{HA_MANAGED_API_PORT}/"
HA_MANAGED_RTSP_PORT = 18554
SIGNAL_SERVER_RESTARTED = f"{DOMAIN}_server_restarted"
# Kept in sync with the go2rtc image pinned in the root Dockerfile by Renovate.
RECOMMENDED_VERSION = "1.9.15"

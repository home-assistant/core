"""Go2rtc constants."""

DOMAIN = "go2rtc"

CONF_DEBUG_UI = "debug_ui"
DEBUG_UI_URL_MESSAGE = "Url and debug_ui cannot be set at the same time."
HA_MANAGED_API_PORT = 11984
HA_MANAGED_URL = f"http://localhost:{HA_MANAGED_API_PORT}/"
# When changing this version, also update the corresponding SHA hash (_GO2RTC_SHA)
# in script/hassfest/docker.py.
RECOMMENDED_VERSION = "1.9.13"

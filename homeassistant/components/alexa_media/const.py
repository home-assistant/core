"""
Support to interface with Alexa Devices.

SPDX-License-Identifier: Apache-2.0

For more details about this platform, please refer to the documentation at
https://community.home-assistant.io/t/echo-devices-alexa-as-media-player-testers-needed/58639
"""
from datetime import timedelta

__version__ = "3.10.8"
PROJECT_URL = "https://github.com/custom-components/alexa_media_player/"
ISSUE_URL = f"{PROJECT_URL}issues"

DOMAIN = "alexa_media"
DATA_ALEXAMEDIA = "alexa_media"

PLAY_SCAN_INTERVAL = 20
SCAN_INTERVAL = timedelta(seconds=60)
MIN_TIME_BETWEEN_SCANS = SCAN_INTERVAL
MIN_TIME_BETWEEN_FORCED_SCANS = timedelta(seconds=1)

ALEXA_COMPONENTS = [
    "media_player",
]
DEPENDENT_ALEXA_COMPONENTS = [
    "notify",
    "switch",
    "sensor",
    "alarm_control_panel",
    "light",
]

HTTP_COOKIE_HEADER = "# HTTP Cookie File"
CONF_ACCOUNTS = "accounts"
CONF_COOKIES_TXT = "cookies_txt"
CONF_DEBUG = "debug"
CONF_HASS_URL = "hass_url"
CONF_INCLUDE_DEVICES = "include_devices"
CONF_EXCLUDE_DEVICES = "exclude_devices"
CONF_QUEUE_DELAY = "queue_delay"
CONF_EXTENDED_ENTITY_DISCOVERY = "extended_entity_discovery"
CONF_SECURITYCODE = "securitycode"
CONF_OTPSECRET = "otp_secret"
CONF_PROXY = "proxy"
CONF_TOTP_REGISTER = "registered"
CONF_OAUTH = "oauth"
CONF_OAUTH_LOGIN = "oauth_login"
DATA_LISTENER = "listener"

EXCEPTION_TEMPLATE = "An exception of type {0} occurred. Arguments:\n{1!r}"

DEFAULT_EXTENDED_ENTITY_DISCOVERY = False
DEFAULT_QUEUE_DELAY = 1.5
SERVICE_CLEAR_HISTORY = "clear_history"
SERVICE_UPDATE_LAST_CALLED = "update_last_called"
SERVICE_FORCE_LOGOUT = "force_logout"

RECURRING_PATTERN = {
    None: "Never Repeat",
    "P1D": "Every day",
    "XXXX-WE": "Weekends",
    "XXXX-WD": "Weekdays",
    "XXXX-WXX-1": "Every Monday",
    "XXXX-WXX-2": "Every Tuesday",
    "XXXX-WXX-3": "Every Wednesday",
    "XXXX-WXX-4": "Every Thursday",
    "XXXX-WXX-5": "Every Friday",
    "XXXX-WXX-6": "Every Saturday",
    "XXXX-WXX-7": "Every Sunday",
}

RECURRING_PATTERN_ISO_SET = {
    None: {},
    "P1D": {1, 2, 3, 4, 5, 6, 7},
    "XXXX-WE": {6, 7},
    "XXXX-WD": {1, 2, 3, 4, 5},
    "XXXX-WXX-1": {1},
    "XXXX-WXX-2": {2},
    "XXXX-WXX-3": {3},
    "XXXX-WXX-4": {4},
    "XXXX-WXX-5": {5},
    "XXXX-WXX-6": {6},
    "XXXX-WXX-7": {7},
}

ATTR_MESSAGE = "message"
ATTR_EMAIL = "email"
ATTR_NUM_ENTRIES = "entries"
STARTUP = """
-------------------------------------------------------------------
{}
Version: {}
This is a custom component
If you have any issues with this you need to open an issue here:
{}
-------------------------------------------------------------------
""".format(
    DOMAIN, __version__, ISSUE_URL
)

AUTH_CALLBACK_PATH = "/auth/alexamedia/callback"
AUTH_CALLBACK_NAME = "auth:alexamedia:callback"
AUTH_PROXY_PATH = "/auth/alexamedia/proxy"
AUTH_PROXY_NAME = "auth:alexamedia:proxy"

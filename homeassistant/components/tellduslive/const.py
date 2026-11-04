"""Consts used by TelldusLive."""

from datetime import timedelta

APPLICATION_NAME = "Home Assistant"

DOMAIN = "tellduslive"

SIGNAL_UPDATE_ENTITY = "tellduslive_update"

KEY_SESSION = "session"
KEY_SCAN_INTERVAL = "scan_interval"

CONF_TOKEN_SECRET = "token_secret"

PUBLIC_KEY = "THUPUNECH5YEQA3RE6UYUPRUZ2DUGUGA"
NOT_SO_PRIVATE_KEY = "PHES7U2RADREWAFEBUSTUBAWRASWUTUS"

SCAN_INTERVAL = timedelta(minutes=1)

ATTR_LAST_UPDATED = "time_last_updated"

TELLDUS_DISCOVERY_NEW = "telldus_new_{}_{}"

CLOUD_NAME = "Cloud API"

TELLDUS_LIVE_API_URL = "https://pa-api.telldus.com/json/"
TELLDUS_LIVE_REQUEST_TOKEN_URL = "https://pa-api.telldus.com/oauth/requestToken"
TELLDUS_LIVE_AUTHORIZE_URL = "https://pa-api.telldus.com/oauth/authorize"
TELLDUS_LIVE_ACCESS_TOKEN_URL = "https://pa-api.telldus.com/oauth/accessToken"

TELLDUS_LOCAL_API_URL = "http://{host}/api/"
TELLDUS_LOCAL_REQUEST_TOKEN_URL = "http://{host}/api/token"
TELLDUS_LOCAL_REFRESH_TOKEN_URL = "http://{host}/api/refreshToken"
TELLDUS_LOCAL_DISCOVERY_PORT = 30303

REQUEST_TIMEOUT = 10

SUPPORTS_LOCAL_API = ["TellstickZnet", "TellstickNetV2"]

TURNON = 1
TURNOFF = 2
BELL = 4
TOGGLE = 8
DIM = 16
LEARN = 32
UP = 128
DOWN = 256
STOP = 512
RGBW = 1024
THERMOSTAT = 2048

SUPPORTED_METHODS = TURNON | TURNOFF | DIM | UP | DOWN | STOP

METHODS = {
    TURNON: "turnOn",
    TURNOFF: "turnOff",
    BELL: "bell",
    TOGGLE: "toggle",
    DIM: "dim",
    LEARN: "learn",
    UP: "up",
    DOWN: "down",
    STOP: "stop",
    RGBW: "rgbw",
    THERMOSTAT: "thermostat",
}

BATTERY_LOW = 255
BATTERY_UNKNOWN = 254
BATTERY_OK = 253

KEY_RETRY_INITIAL_DELAY = "retry_initial_delay"
KEY_RETRY_MAX_DELAY = "retry_max_delay"
KEY_REQUEST_DELAY = "request_delay"

DEFAULT_RETRY_INITIAL_DELAY = 30
DEFAULT_RETRY_MAX_DELAY = 900
DEFAULT_REQUEST_DELAY = 1

STORAGE_VERSION = 1
SNAPSHOT_SAVE_DELAY = 10

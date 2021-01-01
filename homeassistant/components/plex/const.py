"""Constants for the Plex component."""
from homeassistant.const import __version__

DOMAIN = "plex"
NAME_FORMAT = "Plex ({})"
COMMON_PLAYERS = ["Plex Web"]

DEFAULT_PORT = 32400
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

PLEXTV_THROTTLE = 60

DEBOUNCE_TIMEOUT = 1
DISPATCHERS = "dispatchers"
GDM_DEBOUNCER = "gdm_debouncer"
GDM_SCANNER = "gdm_scanner"
PLATFORMS = frozenset(["media_player", "sensor"])
PLATFORMS_COMPLETED = "platforms_completed"
PLAYER_SOURCE = "player_source"
SERVERS = "servers"
WEBSOCKETS = "websockets"

PLEX_SERVER_CONFIG = "server_config"

PLEX_NEW_MP_SIGNAL = "plex_new_mp_signal.{}"
PLEX_UPDATE_MEDIA_PLAYER_SESSION_SIGNAL = "plex_update_session_signal.{}"
PLEX_UPDATE_MEDIA_PLAYER_SIGNAL = "plex_update_mp_signal.{}"
PLEX_UPDATE_PLATFORMS_SIGNAL = "plex_update_platforms_signal.{}"
PLEX_UPDATE_SENSOR_SIGNAL = "plex_update_sensor_signal.{}"

CONF_SERVER = "server"
CONF_SERVER_IDENTIFIER = "server_id"
CONF_USE_EPISODE_ART = "use_episode_art"
CONF_IGNORE_NEW_SHARED_USERS = "ignore_new_shared_users"
CONF_IGNORE_PLEX_WEB_CLIENTS = "ignore_plex_web_clients"
CONF_MONITORED_USERS = "monitored_users"

AUTH_CALLBACK_PATH = "/auth/plex/callback"
AUTH_CALLBACK_NAME = "auth:plex:callback"

X_PLEX_DEVICE_NAME = "Home Assistant"
X_PLEX_PLATFORM = "Home Assistant"
X_PLEX_PRODUCT = "Home Assistant"
X_PLEX_VERSION = __version__

AUTOMATIC_SETUP_STRING = "Obtain a new token from plex.tv"
MANUAL_SETUP_STRING = "Configure Plex server manually"

SERVICE_PLAY_ON_SONOS = "play_on_sonos"
SERVICE_REFRESH_LIBRARY = "refresh_library"
SERVICE_SCAN_CLIENTS = "scan_for_clients"

PLEX_URI_SCHEME = "plex://"

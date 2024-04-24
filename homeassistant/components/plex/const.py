"""Constants for the Plex component."""

from datetime import timedelta
from typing import Final

from homeassistant.const import Platform, __version__

DOMAIN = "plex"
NAME_FORMAT = "Plex ({})"
COMMON_PLAYERS = ["Plex Web"]
TRANSIENT_DEVICE_MODELS = ["Plex Web", "Plex for Sonos"]

DEFAULT_PORT = 32400
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

PLEXTV_THROTTLE = 60

CLIENT_SCAN_INTERVAL = timedelta(minutes=10)
DEBOUNCE_TIMEOUT = 1
DISPATCHERS: Final = "dispatchers"
GDM_DEBOUNCER: Final = "gdm_debouncer"
GDM_SCANNER: Final = "gdm_scanner"
PLATFORMS = frozenset(
    [Platform.BUTTON, Platform.MEDIA_PLAYER, Platform.SENSOR, Platform.UPDATE]
)
PLAYER_SOURCE = "player_source"
SERVERS: Final = "servers"
WEBSOCKETS: Final = "websockets"

PLEX_SERVER_CONFIG = "server_config"

PLEX_NEW_MP_SIGNAL = "plex_new_mp_signal.{}"
PLEX_UPDATE_MEDIA_PLAYER_SESSION_SIGNAL = "plex_update_session_signal.{}"
PLEX_UPDATE_MEDIA_PLAYER_SIGNAL = "plex_update_mp_signal.{}"
PLEX_UPDATE_LIBRARY_SIGNAL = "plex_update_libraries_signal.{}"
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

SERVICE_REFRESH_LIBRARY = "refresh_library"
SERVICE_SCAN_CLIENTS = "scan_for_clients"

PLEX_URI_SCHEME = "plex://"

INVALID_TOKEN_MESSAGE = "Invalid token"

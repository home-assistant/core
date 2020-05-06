"""Constants for the Plex component."""
from homeassistant.const import __version__

DOMAIN = "plex"
NAME_FORMAT = "Plex ({})"
COMMON_PLAYERS = ["Plex Web"]

DEFAULT_PORT = 32400
DEFAULT_SSL = False
DEFAULT_VERIFY_SSL = True

DEBOUNCE_TIMEOUT = 1
DISPATCHERS = "dispatchers"
PLATFORMS = frozenset(["media_player", "sensor"])
PLATFORMS_COMPLETED = "platforms_completed"
SERVERS = "servers"
WEBSOCKETS = "websockets"

PLEX_MEDIA_PLAYER_OPTIONS = "plex_mp_options"
PLEX_SERVER_CONFIG = "server_config"

PLEX_NEW_MP_SIGNAL = "plex_new_mp_signal.{}"
PLEX_UPDATE_MEDIA_PLAYER_SIGNAL = "plex_update_mp_signal.{}"
PLEX_UPDATE_PLATFORMS_SIGNAL = "plex_update_platforms_signal.{}"
PLEX_UPDATE_SENSOR_SIGNAL = "plex_update_sensor_signal.{}"

CONF_CLIENT_IDENTIFIER = "client_id"
CONF_SERVER = "server"
CONF_SERVER_IDENTIFIER = "server_id"
CONF_USE_EPISODE_ART = "use_episode_art"
CONF_SHOW_ALL_CONTROLS = "show_all_controls"
CONF_IGNORE_NEW_SHARED_USERS = "ignore_new_shared_users"
CONF_MONITORED_USERS = "monitored_users"

AUTH_CALLBACK_PATH = "/auth/plex/callback"
AUTH_CALLBACK_NAME = "auth:plex:callback"

X_PLEX_DEVICE_NAME = "Home Assistant"
X_PLEX_PLATFORM = "Home Assistant"
X_PLEX_PRODUCT = "Home Assistant"
X_PLEX_VERSION = __version__

AUTOMATIC_SETUP_STRING = "Obtain a new token from plex.tv"
MANUAL_SETUP_STRING = "Configure Plex server manually"

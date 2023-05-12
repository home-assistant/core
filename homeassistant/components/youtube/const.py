"""Constants for Youtube integration."""
import logging

DEFAULT_ACCESS = ["https://www.googleapis.com/auth/youtube.readonly"]
DOMAIN = "youtube"
MANUFACTURER = "Google, Inc."

CONF_CHANNELS = "channels"
CONF_ID = "id"
CONF_UPLOAD_PLAYLIST = "upload_playlist_id"
DATA_AUTH = "auth"
DATA_HASS_CONFIG = "hass_config"
COORDINATOR = "coordinator"
AUTH = "auth"

LOGGER = logging.getLogger(__package__)

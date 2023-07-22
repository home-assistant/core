"""Constants for YouTube integration."""
import logging

DEFAULT_ACCESS = ["https://www.googleapis.com/auth/youtube.readonly"]
DOMAIN = "youtube"
MANUFACTURER = "Google, Inc."
CHANNEL_CREATION_HELP_URL = "https://support.google.com/youtube/answer/1646861"

CONF_CHANNELS = "channels"
CONF_ID = "id"
CONF_UPLOAD_PLAYLIST = "upload_playlist_id"
COORDINATOR = "coordinator"
AUTH = "auth"

LOGGER = logging.getLogger(__package__)

ATTR_TITLE = "title"
ATTR_VIDEO_ID = "video_id"
ATTR_PUBLISHED_AT = "published_at"

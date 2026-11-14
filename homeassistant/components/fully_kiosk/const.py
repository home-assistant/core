"""Constants for the Fully Kiosk Browser integration."""

from datetime import timedelta
import logging
from typing import Final

from homeassistant.components.media_player import MediaPlayerEntityFeature

DOMAIN: Final = "fully_kiosk"

LOGGER = logging.getLogger(__package__)
UPDATE_INTERVAL = timedelta(seconds=30)
UPDATE_FEED_INTERVAL = timedelta(hours=12)

DEFAULT_PORT = 2323

UPDATE_FEED_URL = "https://www.fully-kiosk.com/feed/media"
VERSION_HISTORY_URL = (
    "https://www.fully-kiosk.com/docs/en/getting-started/version-history"
)

AUDIOMANAGER_STREAM_MUSIC = 3

MEDIA_SUPPORT_FULLYKIOSK = (
    MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.BROWSE_MEDIA
)

"""Constants for Podcast Player."""

from datetime import timedelta
from typing import Final

DOMAIN: Final = "podcast_player"

EVENT_NEW_EPISODE: Final = "new_episode"
MAX_BROWSE_EPISODES: Final = 250
SCAN_INTERVAL: Final = timedelta(hours=1)

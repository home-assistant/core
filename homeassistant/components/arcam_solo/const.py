"""Constants for the Arcam Solo integration."""

from homeassistant.components.media_player import MediaPlayerState

DOMAIN = "arcam_solo"

PLAYABLE_SOURCES = ("CD", "USB")
TRACK_SOURCES = ("CD", "USB", "DAB", "FM", "AM")
MUSIC_SOURCES = ("CD", "USB", "DAB", "FM", "AM")
NAVIGATION_SOURCES = ("DAB", "AM", "FM")
MAX_VOLUME = 72
CD_STATE_MAP: dict[str, MediaPlayerState] = {
    "Paused": MediaPlayerState.PAUSED,
    "Loading": MediaPlayerState.BUFFERING,
    "Stopped": MediaPlayerState.IDLE,
    "Playing": MediaPlayerState.PLAYING,
    "Scanning Back": MediaPlayerState.BUFFERING,
    "Scanning Forward": MediaPlayerState.BUFFERING,
    "Tray Open / Empty": MediaPlayerState.ON,
    "Track Skipping": MediaPlayerState.BUFFERING,
}

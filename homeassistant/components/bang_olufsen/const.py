"""Constants for the Bang & Olufsen integration."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from mozart_api.models import Source, SourceArray, SourceTypeEnum

from homeassistant.components.media_player import MediaPlayerState, MediaType


class BangOlufsenSource:
    """Class used for associating device source ids with friendly names. May not include all sources."""

    URI_STREAMER: Final[Source] = Source(name="Audio Streamer", id="uriStreamer")
    BLUETOOTH: Final[Source] = Source(name="Bluetooth", id="bluetooth")
    CHROMECAST: Final[Source] = Source(name="Chromecast built-in", id="chromeCast")
    LINE_IN: Final[Source] = Source(name="Line-In", id="lineIn")
    SPDIF: Final[Source] = Source(name="Optical", id="spdif")
    NET_RADIO: Final[Source] = Source(name="B&O Radio", id="netRadio")
    DEEZER: Final[Source] = Source(name="Deezer", id="deezer")
    TIDAL: Final[Source] = Source(name="Tidal", id="tidal")


BANG_OLUFSEN_STATES: dict[str, MediaPlayerState] = {
    # Dict used for translating device states to Home Assistant states.
    "started": MediaPlayerState.PLAYING,
    "buffering": MediaPlayerState.PLAYING,
    "idle": MediaPlayerState.IDLE,
    "paused": MediaPlayerState.PAUSED,
    "stopped": MediaPlayerState.PAUSED,
    "ended": MediaPlayerState.PAUSED,
    "error": MediaPlayerState.IDLE,
    # A device's initial state is "unknown" and should be treated as "idle"
    "unknown": MediaPlayerState.IDLE,
}


# Media types for play_media
class BangOlufsenMediaType(StrEnum):
    """Bang & Olufsen specific media types."""

    FAVOURITE = "favourite"
    DEEZER = "deezer"
    RADIO = "radio"
    TIDAL = "tidal"
    TTS = "provider"
    OVERLAY_TTS = "overlay_tts"


class BangOlufsenModel(StrEnum):
    """Enum for compatible model names."""

    BEOCONNECT_CORE = "Beoconnect Core"
    BEOLAB_8 = "BeoLab 8"
    BEOLAB_28 = "BeoLab 28"
    BEOSOUND_2 = "Beosound 2 3rd Gen"
    BEOSOUND_A5 = "Beosound A5"
    BEOSOUND_A9 = "Beosound A9 5th Gen"
    BEOSOUND_BALANCE = "Beosound Balance"
    BEOSOUND_EMERGE = "Beosound Emerge"
    BEOSOUND_LEVEL = "Beosound Level"
    BEOSOUND_THEATRE = "Beosound Theatre"


# Dispatcher events
class WebsocketNotification(StrEnum):
    """Enum for WebSocket notification types."""

    ACTIVE_LISTENING_MODE = "active_listening_mode"
    PLAYBACK_ERROR = "playback_error"
    PLAYBACK_METADATA = "playback_metadata"
    PLAYBACK_PROGRESS = "playback_progress"
    PLAYBACK_SOURCE = "playback_source"
    PLAYBACK_STATE = "playback_state"
    SOFTWARE_UPDATE_STATE = "software_update_state"
    SOURCE_CHANGE = "source_change"
    VOLUME = "volume"

    # Sub-notifications
    BEOLINK = "beolink"
    BEOLINK_PEERS = "beolinkPeers"
    BEOLINK_LISTENERS = "beolinkListeners"
    BEOLINK_AVAILABLE_LISTENERS = "beolinkAvailableListeners"
    CONFIGURATION = "configuration"
    NOTIFICATION = "notification"
    REMOTE_MENU_CHANGED = "remoteMenuChanged"

    ALL = "all"


DOMAIN: Final[str] = "bang_olufsen"

# Default values for configuration.
DEFAULT_MODEL: Final[str] = BangOlufsenModel.BEOSOUND_BALANCE

# Configuration.
CONF_SERIAL_NUMBER: Final = "serial_number"
CONF_BEOLINK_JID: Final = "jid"

# Models to choose from in manual configuration.
COMPATIBLE_MODELS: list[str] = [x.value for x in BangOlufsenModel]

# Attribute names for zeroconf discovery.
ATTR_TYPE_NUMBER: Final[str] = "tn"
ATTR_SERIAL_NUMBER: Final[str] = "sn"
ATTR_ITEM_NUMBER: Final[str] = "in"
ATTR_FRIENDLY_NAME: Final[str] = "fn"

# Power states.
BANG_OLUFSEN_ON: Final[str] = "on"

VALID_MEDIA_TYPES: Final[tuple] = (
    BangOlufsenMediaType.FAVOURITE,
    BangOlufsenMediaType.DEEZER,
    BangOlufsenMediaType.RADIO,
    BangOlufsenMediaType.TTS,
    BangOlufsenMediaType.TIDAL,
    BangOlufsenMediaType.OVERLAY_TTS,
    MediaType.MUSIC,
    MediaType.URL,
    MediaType.CHANNEL,
)

# Sources on the device that should not be selectable by the user
HIDDEN_SOURCE_IDS: Final[tuple] = (
    "airPlay",
    "bluetooth",
    "chromeCast",
    "generator",
    "local",
    "dlna",
    "qplay",
    "wpl",
    "pl",
    "beolink",
    "usbIn",
)

# Fallback sources to use in case of API failure.
FALLBACK_SOURCES: Final[SourceArray] = SourceArray(
    items=[
        Source(
            id="uriStreamer",
            is_enabled=True,
            is_playable=False,
            name="Audio Streamer",
            type=SourceTypeEnum(value="uriStreamer"),
        ),
        Source(
            id="bluetooth",
            is_enabled=True,
            is_playable=False,
            name="Bluetooth",
            type=SourceTypeEnum(value="bluetooth"),
        ),
        Source(
            id="spotify",
            is_enabled=True,
            is_playable=False,
            name="Spotify Connect",
            type=SourceTypeEnum(value="spotify"),
        ),
        Source(
            id="lineIn",
            is_enabled=True,
            is_playable=True,
            name="Line-In",
            type=SourceTypeEnum(value="lineIn"),
        ),
        Source(
            id="spdif",
            is_enabled=True,
            is_playable=True,
            name="Optical",
            type=SourceTypeEnum(value="spdif"),
        ),
        Source(
            id="netRadio",
            is_enabled=True,
            is_playable=True,
            name="B&O Radio",
            type=SourceTypeEnum(value="netRadio"),
        ),
        Source(
            id="deezer",
            is_enabled=True,
            is_playable=True,
            name="Deezer",
            type=SourceTypeEnum(value="deezer"),
        ),
        Source(
            id="tidalConnect",
            is_enabled=True,
            is_playable=True,
            name="Tidal Connect",
            type=SourceTypeEnum(value="tidalConnect"),
        ),
    ]
)


# Device events
BANG_OLUFSEN_WEBSOCKET_EVENT: Final[str] = f"{DOMAIN}_websocket_event"


CONNECTION_STATUS: Final[str] = "CONNECTION_STATUS"

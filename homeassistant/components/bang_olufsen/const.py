"""Constants for the Bang & Olufsen integration."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from mozart_api.models import Source, SourceArray, SourceTypeEnum

from homeassistant.components.media_player import MediaPlayerState, MediaType


class SOURCE_ENUM(StrEnum):
    """Enum used for associating device source ids with friendly names. May not include all sources."""

    uriStreamer = "Audio Streamer"  # noqa: N815
    bluetooth = "Bluetooth"
    airPlay = "AirPlay"  # noqa: N815
    chromeCast = "Chromecast built-in"  # noqa: N815
    spotify = "Spotify Connect"
    generator = "Tone Generator"
    lineIn = "Line-In"  # noqa: N815
    spdif = "Optical"
    netRadio = "B&O Radio"  # noqa: N815
    local = "Local"
    dlna = "DLNA"
    qplay = "QPlay"
    wpl = "Wireless Powerlink"
    pl = "Powerlink"
    tv = "TV"
    deezer = "Deezer"
    beolink = "Networklink"
    tidalConnect = "Tidal Connect"  # noqa: N815


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
class BANG_OLUFSEN_MEDIA_TYPE(StrEnum):
    """Bang & Olufsen specific media types."""

    FAVOURITE = "favourite"
    DEEZER = "deezer"
    RADIO = "radio"
    TTS = "provider"


class MODEL_ENUM(StrEnum):
    """Enum for compatible model names."""

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
class WEBSOCKET_NOTIFICATION(StrEnum):
    """Enum for WebSocket notification types."""

    PLAYBACK_ERROR: Final[str] = "playback_error"
    PLAYBACK_METADATA: Final[str] = "playback_metadata"
    PLAYBACK_PROGRESS: Final[str] = "playback_progress"
    PLAYBACK_SOURCE: Final[str] = "playback_source"
    PLAYBACK_STATE: Final[str] = "playback_state"
    SOFTWARE_UPDATE_STATE: Final[str] = "software_update_state"
    SOURCE_CHANGE: Final[str] = "source_change"
    VOLUME: Final[str] = "volume"

    # Sub-notifications
    NOTIFICATION: Final[str] = "notification"
    REMOTE_MENU_CHANGED: Final[str] = "remoteMenuChanged"

    ALL: Final[str] = "all"


DOMAIN: Final[str] = "bang_olufsen"

# Default values for configuration.
DEFAULT_MODEL: Final[str] = MODEL_ENUM.BEOSOUND_BALANCE

# Configuration.
CONF_SERIAL_NUMBER: Final = "serial_number"
CONF_BEOLINK_JID: Final = "jid"

# Models to choose from in manual configuration.
COMPATIBLE_MODELS: list[str] = [x.value for x in MODEL_ENUM]

# Attribute names for zeroconf discovery.
ATTR_TYPE_NUMBER: Final[str] = "tn"
ATTR_SERIAL_NUMBER: Final[str] = "sn"
ATTR_ITEM_NUMBER: Final[str] = "in"
ATTR_FRIENDLY_NAME: Final[str] = "fn"

# Power states.
BANG_OLUFSEN_ON: Final[str] = "on"

VALID_MEDIA_TYPES: Final[tuple] = (
    BANG_OLUFSEN_MEDIA_TYPE.FAVOURITE,
    BANG_OLUFSEN_MEDIA_TYPE.DEEZER,
    BANG_OLUFSEN_MEDIA_TYPE.RADIO,
    BANG_OLUFSEN_MEDIA_TYPE.TTS,
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

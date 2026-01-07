"""Constants for the Bang & Olufsen integration."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from mozart_api.models import Source, SourceArray, SourceTypeEnum

from homeassistant.components.media_player import (
    MediaPlayerState,
    MediaType,
    RepeatMode,
)


class BeoSource:
    """Class used for associating device source ids with friendly names. May not include all sources."""

    DEEZER: Final[Source] = Source(name="Deezer", id="deezer")
    LINE_IN: Final[Source] = Source(name="Line-In", id="lineIn")
    NET_RADIO: Final[Source] = Source(name="B&O Radio", id="netRadio")
    SPDIF: Final[Source] = Source(name="Optical", id="spdif")
    TIDAL: Final[Source] = Source(name="Tidal", id="tidal")
    TV: Final[Source] = Source(name="TV", id="tv")
    UNKNOWN: Final[Source] = Source(name="Unknown Source", id="unknown")
    URI_STREAMER: Final[Source] = Source(name="Audio Streamer", id="uriStreamer")


BEO_STATES: dict[str, MediaPlayerState] = {
    # Dict used for translating device states to Home Assistant states.
    "started": MediaPlayerState.PLAYING,
    "buffering": MediaPlayerState.PLAYING,
    "idle": MediaPlayerState.IDLE,
    "paused": MediaPlayerState.PAUSED,
    "stopped": MediaPlayerState.IDLE,
    "ended": MediaPlayerState.PAUSED,
    "error": MediaPlayerState.IDLE,
    # A device's initial state is "unknown" and should be treated as "idle"
    "unknown": MediaPlayerState.IDLE,
}

# Dict used for translating Home Assistant settings to device repeat settings.
BEO_REPEAT_FROM_HA: dict[RepeatMode, str] = {
    RepeatMode.ALL: "all",
    RepeatMode.ONE: "track",
    RepeatMode.OFF: "none",
}
# Dict used for translating device repeat settings to Home Assistant settings.
BEO_REPEAT_TO_HA: dict[str, RepeatMode] = {
    value: key for key, value in BEO_REPEAT_FROM_HA.items()
}


# Media types for play_media
class BeoMediaType(StrEnum):
    """Bang & Olufsen specific media types."""

    DEEZER = "deezer"
    FAVOURITE = "favourite"
    OVERLAY_TTS = "overlay_tts"
    RADIO = "radio"
    TIDAL = "tidal"
    TTS = "provider"
    TV = "tv"


class BeoModel(StrEnum):
    """Enum for compatible model names."""

    # Mozart devices
    BEOCONNECT_CORE = "Beoconnect Core"
    BEOLAB_8 = "BeoLab 8"
    BEOLAB_28 = "BeoLab 28"
    BEOSOUND_2 = "Beosound 2 3rd Gen"
    BEOSOUND_A5 = "Beosound A5"
    BEOSOUND_A9 = "Beosound A9 5th Gen"
    BEOSOUND_BALANCE = "Beosound Balance"
    BEOSOUND_EMERGE = "Beosound Emerge"
    BEOSOUND_LEVEL = "Beosound Level"
    BEOSOUND_PREMIERE = "Beosound Premiere"
    BEOSOUND_THEATRE = "Beosound Theatre"
    # Remote devices
    BEOREMOTE_ONE = "Beoremote One"


class BeoAttribute(StrEnum):
    """Enum for extra_state_attribute keys."""

    BEOLINK = "beolink"
    BEOLINK_PEERS = "peers"
    BEOLINK_SELF = "self"
    BEOLINK_LEADER = "leader"
    BEOLINK_LISTENERS = "listeners"


# Physical "buttons" on devices
class BeoButtons(StrEnum):
    """Enum for device buttons."""

    BLUETOOTH = "Bluetooth"
    MICROPHONE = "Microphone"
    NEXT = "Next"
    PLAY_PAUSE = "PlayPause"
    PRESET_1 = "Preset1"
    PRESET_2 = "Preset2"
    PRESET_3 = "Preset3"
    PRESET_4 = "Preset4"
    PREVIOUS = "Previous"
    VOLUME = "Volume"


# Dispatcher events
class WebsocketNotification(StrEnum):
    """Enum for WebSocket notification types."""

    ACTIVE_LISTENING_MODE = "active_listening_mode"
    BEO_REMOTE_BUTTON = "beo_remote_button"
    BUTTON = "button"
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
    REMOTE_CONTROL_DEVICES = "remoteControlDevices"
    REMOTE_MENU_CHANGED = "remoteMenuChanged"

    ALL = "all"


DOMAIN: Final[str] = "bang_olufsen"

# Default values for configuration.
DEFAULT_MODEL: Final[str] = BeoModel.BEOSOUND_BALANCE

# Configuration.
CONF_SERIAL_NUMBER: Final = "serial_number"
CONF_BEOLINK_JID: Final = "jid"

# Models to choose from in manual configuration.
SELECTABLE_MODELS: list[str] = [
    model.value for model in BeoModel if model != BeoModel.BEOREMOTE_ONE
]

MANUFACTURER: Final[str] = "Bang & Olufsen"

# Attribute names for zeroconf discovery.
ATTR_TYPE_NUMBER: Final[str] = "tn"
ATTR_SERIAL_NUMBER: Final[str] = "sn"
ATTR_ITEM_NUMBER: Final[str] = "in"
ATTR_FRIENDLY_NAME: Final[str] = "fn"

# Power states.
BEO_ON: Final[str] = "on"

VALID_MEDIA_TYPES: Final[tuple] = (
    BeoMediaType.FAVOURITE,
    BeoMediaType.DEEZER,
    BeoMediaType.RADIO,
    BeoMediaType.TTS,
    BeoMediaType.TIDAL,
    BeoMediaType.OVERLAY_TTS,
    MediaType.MUSIC,
    MediaType.URL,
    MediaType.CHANNEL,
)


# Fallback sources to use in case of API failure.
FALLBACK_SOURCES: Final[SourceArray] = SourceArray(
    items=[
        Source(
            id="uriStreamer",
            is_enabled=True,
            is_playable=True,
            name="Audio Streamer",
            type=SourceTypeEnum(value="uriStreamer"),
            is_seekable=False,
        ),
        Source(
            id="bluetooth",
            is_enabled=True,
            is_playable=True,
            name="Bluetooth",
            type=SourceTypeEnum(value="bluetooth"),
            is_seekable=False,
        ),
        Source(
            id="spotify",
            is_enabled=True,
            is_playable=True,
            name="Spotify Connect",
            type=SourceTypeEnum(value="spotify"),
            is_seekable=True,
        ),
        Source(
            id="lineIn",
            is_enabled=True,
            is_playable=True,
            name="Line-In",
            type=SourceTypeEnum(value="lineIn"),
            is_seekable=False,
        ),
        Source(
            id="spdif",
            is_enabled=True,
            is_playable=True,
            name="Optical",
            type=SourceTypeEnum(value="spdif"),
            is_seekable=False,
        ),
        Source(
            id="netRadio",
            is_enabled=True,
            is_playable=True,
            name="B&O Radio",
            type=SourceTypeEnum(value="netRadio"),
            is_seekable=False,
        ),
        Source(
            id="deezer",
            is_enabled=True,
            is_playable=True,
            name="Deezer",
            type=SourceTypeEnum(value="deezer"),
            is_seekable=True,
        ),
        Source(
            id="tidalConnect",
            is_enabled=True,
            is_playable=True,
            name="Tidal Connect",
            type=SourceTypeEnum(value="tidalConnect"),
            is_seekable=True,
        ),
    ]
)

# Device events
BEO_WEBSOCKET_EVENT: Final[str] = f"{DOMAIN}_websocket_event"

# Dict used to translate native Bang & Olufsen event names to string.json compatible ones
EVENT_TRANSLATION_MAP: dict[str, str] = {
    # Beoremote One
    "KeyPress": "key_press",
    "KeyRelease": "key_release",
    # Physical "buttons"
    "shortPress (Release)": "short_press_release",
    "longPress (Timeout)": "long_press_timeout",
    "longPress (Release)": "long_press_release",
    "veryLongPress (Timeout)": "very_long_press_timeout",
    "veryLongPress (Release)": "very_long_press_release",
}

CONNECTION_STATUS: Final[str] = "CONNECTION_STATUS"

DEVICE_BUTTONS: Final[list[str]] = [x.value for x in BeoButtons]


DEVICE_BUTTON_EVENTS: Final[list[str]] = [
    "short_press_release",
    "long_press_timeout",
    "long_press_release",
    "very_long_press_timeout",
    "very_long_press_release",
]

BEO_REMOTE_SUBMENU_CONTROL: Final[str] = "Control"
BEO_REMOTE_SUBMENU_LIGHT: Final[str] = "Light"

# Common for both submenus
BEO_REMOTE_KEYS: Final[tuple[str, ...]] = (
    "Blue",
    "Digit0",
    "Digit1",
    "Digit2",
    "Digit3",
    "Digit4",
    "Digit5",
    "Digit6",
    "Digit7",
    "Digit8",
    "Digit9",
    "Down",
    "Green",
    "Left",
    "Play",
    "Red",
    "Rewind",
    "Right",
    "Select",
    "Stop",
    "Up",
    "Wind",
    "Yellow",
    "Func1",
    "Func2",
    "Func3",
    "Func4",
    "Func5",
    "Func6",
    "Func7",
    "Func8",
    "Func9",
    "Func10",
    "Func11",
    "Func12",
    "Func13",
    "Func14",
    "Func15",
    "Func16",
    "Func17",
)

# "keys" that are unique to the Control submenu
BEO_REMOTE_CONTROL_KEYS: Final[tuple[str, ...]] = (
    "Func18",
    "Func19",
    "Func20",
    "Func21",
    "Func22",
    "Func23",
    "Func24",
    "Func25",
    "Func26",
    "Func27",
)

BEO_REMOTE_KEY_EVENTS: Final[list[str]] = ["key_press", "key_release"]


# Beolink Converter NL/ML sources need to be transformed to upper case
BEOLINK_JOIN_SOURCES_TO_UPPER = (
    "aux_a",
    "cd",
    "ph",
    "radio",
    "tp1",
    "tp2",
)
BEOLINK_JOIN_SOURCES = (
    *BEOLINK_JOIN_SOURCES_TO_UPPER,
    "beoradio",
    "deezer",
    "spotify",
    "tidal",
)

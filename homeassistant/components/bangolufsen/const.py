"""Constants for the Bang & Olufsen integration."""

from __future__ import annotations

from enum import Enum, StrEnum
import logging
from typing import Final, cast

from mozart_api.models import (
    PlaybackContentMetadata,
    PlaybackProgress,
    RenderingState,
    Source,
    SourceArray,
    SourceTypeEnum,
    VolumeLevel,
    VolumeMute,
    VolumeState,
)
from mozart_api.mozart_client import MozartClient

from homeassistant.components.media_player import MediaPlayerState, MediaType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry


class ART_SIZE_ENUM(Enum):
    """Enum used for sorting images that have size defined by a string."""

    small = 1
    medium = 2
    large = 3


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


class REPEAT_ENUM(StrEnum):
    """Enum used for translating device repeat settings to Home Assistant settings."""

    all = "all"
    one = "track"
    off = "none"


BANGOLUFSEN_STATES: dict[str, MediaPlayerState] = {
    # Dict used for translating device states to Home Assistant states.
    "started": MediaPlayerState.PLAYING,
    "buffering": MediaPlayerState.PLAYING,
    "idle": MediaPlayerState.IDLE,
    "paused": MediaPlayerState.PAUSED,
    "stopped": MediaPlayerState.PAUSED,
    "ended": MediaPlayerState.PAUSED,
    "error": MediaPlayerState.IDLE,
    # A devices initial state is "unknown" and should be treated as "idle"
    "unknown": MediaPlayerState.IDLE,
    # Power states
}


# Media types for play_media
class BANGOLUFSEN_MEDIA_TYPE(StrEnum):
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


class ENTITY_ENUM(StrEnum):
    """Enum for accessing and storing the entities in hass."""

    MEDIA_PLAYER = "media_player"
    WEBSOCKET = "websocket"


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


DOMAIN: Final[str] = "bangolufsen"

# Default values for configuration.
DEFAULT_DEFAULT_VOLUME: Final[int] = 40
DEFAULT_MAX_VOLUME: Final[int] = 100
DEFAULT_VOLUME_STEP: Final[int] = 5
DEFAULT_MODEL: Final[str] = MODEL_ENUM.BEOSOUND_BALANCE

# Acceptable ranges for configuration.
DEFAULT_VOLUME_RANGE: Final[range] = range(1, 70, 1)
MAX_VOLUME_RANGE: Final[range] = range(20, 100, 1)
VOLUME_STEP_RANGE: Final[range] = range(1, 20, 1)

# Configuration.
CONF_DEFAULT_VOLUME: Final = "default_volume"
CONF_MAX_VOLUME: Final = "max_volume"
CONF_VOLUME_STEP: Final = "volume_step"
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
BANGOLUFSEN_ON: Final[str] = "on"

VALID_MEDIA_TYPES: Final[tuple] = (
    BANGOLUFSEN_MEDIA_TYPE.FAVOURITE,
    BANGOLUFSEN_MEDIA_TYPE.DEEZER,
    BANGOLUFSEN_MEDIA_TYPE.RADIO,
    BANGOLUFSEN_MEDIA_TYPE.TTS,
    MediaType.MUSIC,
    MediaType.URL,
    MediaType.CHANNEL,
)

# Playback states for playing and not playing
PLAYING: Final[tuple] = ("started", "buffering", BANGOLUFSEN_ON)
NOT_PLAYING: Final[tuple] = ("idle", "paused", "stopped", "ended", "unknown", "error")

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
    "classicsAdapter",
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
BANGOLUFSEN_WEBSOCKET_EVENT: Final[str] = f"{DOMAIN}_websocket_event"


CONNECTION_STATUS: Final[str] = "CONNECTION_STATUS"

# Misc.
WEBSOCKET_CONNECTION_DELAY: Final[float] = 3.0


def get_device(hass: HomeAssistant | None, unique_id: str) -> DeviceEntry | None:
    """Get the device."""
    if not isinstance(hass, HomeAssistant):
        return None

    device_registry = dr.async_get(hass)
    device = cast(DeviceEntry, device_registry.async_get_device({(DOMAIN, unique_id)}))
    return device


class BangOlufsenVariables:
    """Shared variables for various classes."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the object."""

        # get the input from the config entry.
        self.entry: ConfigEntry = entry

        # Set the configuration variables.
        self._host: str = self.entry.data[CONF_HOST]
        self._name: str = self.entry.title
        self._unique_id: str = cast(str, self.entry.unique_id)

        self._client: MozartClient = MozartClient(
            host=self._host,
            websocket_reconnect=True,
            urllib3_logging_level=logging.ERROR,
        )

        # Objects that get directly updated by notifications.
        self._playback_metadata: PlaybackContentMetadata = PlaybackContentMetadata()
        self._playback_progress: PlaybackProgress = PlaybackProgress(total_duration=0)
        self._playback_source: Source = Source()
        self._playback_state: RenderingState = RenderingState()
        self._source_change: Source = Source()
        self._volume: VolumeState = VolumeState(
            level=VolumeLevel(level=0), muted=VolumeMute(muted=False)
        )

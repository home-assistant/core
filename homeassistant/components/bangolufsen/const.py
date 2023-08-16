"""Constants for the Bang & Olufsen integration."""

from __future__ import annotations

from enum import Enum, StrEnum
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
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity


class ArtSizeEnum(Enum):
    """Enum used for sorting images that have size defined by a string."""

    small = 1
    medium = 2
    large = 3


class SourceEnum(StrEnum):
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


class RepeatEnum(StrEnum):
    """Enum used for translating device repeat settings to Home Assistant settings."""

    all = "all"
    one = "track"
    off = "none"


class StateEnum(StrEnum):
    """Enum used for translating device states to Home Assistant states."""

    # Playback states
    started = MediaPlayerState.PLAYING
    buffering = MediaPlayerState.PLAYING
    idle = MediaPlayerState.IDLE
    paused = MediaPlayerState.PAUSED
    stopped = MediaPlayerState.PAUSED
    ended = MediaPlayerState.PAUSED
    error = MediaPlayerState.IDLE
    # A devices initial state is "unknown" and should be treated as "idle"
    unknown = MediaPlayerState.IDLE

    # Power states
    networkStandby = MediaPlayerState.IDLE  # noqa: N815


# Media types for play_media
class BangOlufsenMediaType(StrEnum):
    """Bang & Olufsen specific media types."""

    FAVOURITE = "favourite"
    DEEZER = "deezer"
    RADIO = "radio"
    TTS = "provider"


class ModelEnum(StrEnum):
    """Enum for compatible model names."""

    beolab_28 = "BeoLab 28"
    beosound_2 = "Beosound 2 3rd Gen"
    beosound_a5 = "Beosound A5"
    beosound_a9 = "Beosound A9 5th Gen"
    beosound_balance = "Beosound Balance"
    beosound_emerge = "Beosound Emerge"
    beosound_level = "Beosound Level"
    beosound_theatre = "Beosound Theatre"


class EntityEnum(StrEnum):
    """Enum for accessing and storing the entities in hass."""

    WEBSOCKET = "websocket"
    MEDIA_PLAYER = "media_player"


# Dispatcher events
class WebSocketNotification(StrEnum):
    """Enum for WebSocket notification types."""

    ACTIVE_LISTENING_MODE: Final[str] = "active_listening_mode"
    ACTIVE_SPEAKER_GROUP: Final[str] = "active_speaker_group"
    ALARM_TRIGGERED: Final[str] = "alarm_triggered"
    BATTERY: Final[str] = "battery"
    BEOLINK_EXPERIENCES_RESULT: Final[str] = "beolink_experiences_result"
    BEOLINK_JOIN_RESULT: Final[str] = "beolink_join_result"
    BEO_REMOTE_BUTTON: Final[str] = "beo_remote_button"
    BUTTON: Final[str] = "button"
    CURTAINS: Final[str] = "curtains"
    PLAYBACK_ERROR: Final[str] = "playback_error"
    PLAYBACK_METADATA: Final[str] = "playback_metadata"
    PLAYBACK_PROGRESS: Final[str] = "playback_progress"
    PLAYBACK_SOURCE: Final[str] = "playback_source"
    PLAYBACK_STATE: Final[str] = "playback_state"
    POWER_STATE: Final[str] = "power_state"
    ROLE: Final[str] = "role"
    SOFTWARE_UPDATE_STATE: Final[str] = "software_update_state"
    SOUND_SETTINGS: Final[str] = "sound_settings"
    SOURCE_CHANGE: Final[str] = "source_change"
    VOLUME: Final[str] = "volume"

    # Sub-notifications
    NOTIFICATION: Final[str] = "notification"
    PROXIMITY: Final[str] = "proximity"
    BEOLINK: Final[str] = "beolink"
    REMOTE_MENU_CHANGED: Final[str] = "remoteMenuChanged"
    CONFIGURATION: Final[str] = "configuration"
    BLUETOOTH_DEVICES: Final[str] = "bluetooth"
    REMOTE_CONTROL_DEVICES: Final[str] = "remoteControlDevices"

    ALL: Final[str] = "all"


DOMAIN: Final[str] = "bangolufsen"

# Default values for configuration.
DEFAULT_HOST: Final[str] = "192.168.1.1"
DEFAULT_DEFAULT_VOLUME: Final[int] = 40
DEFAULT_MAX_VOLUME: Final[int] = 100
DEFAULT_VOLUME_STEP: Final[int] = 5
DEFAULT_MODEL: Final[str] = ModelEnum.beosound_balance

# Acceptable ranges for configuration.
DEFAULT_VOLUME_RANGE: Final[range] = range(1, (70 + 1), 1)
MAX_VOLUME_RANGE: Final[range] = range(20, (100 + 1), 1)
VOLUME_STEP_RANGE: Final[range] = range(1, (20 + 1), 1)

# Abort reasons for configuration.
API_EXCEPTION: Final[str] = "api_exception"
MAX_RETRY_ERROR: Final[str] = "max_retry_error"
NEW_CONNECTION_ERROR: Final[str] = "new_connection_error"
NO_DEVICE: Final[str] = "no_device"
VALUE_ERROR: Final[str] = "value_error"
NOT_MOZART_DEVICE: Final[str] = "not_mozart_device"


# Configuration.
CONF_DEFAULT_VOLUME: Final = "default_volume"
CONF_MAX_VOLUME: Final = "max_volume"
CONF_VOLUME_STEP: Final = "volume_step"
CONF_SERIAL_NUMBER: Final = "serial_number"
CONF_BEOLINK_JID: Final = "jid"

# Models to choose from in manual configuration.
COMPATIBLE_MODELS: list[str] = [x.value for x in ModelEnum]

# Attribute names for zeroconf discovery.
ATTR_TYPE_NUMBER: Final[str] = "tn"
ATTR_SERIAL_NUMBER: Final[str] = "sn"
ATTR_ITEM_NUMBER: Final[str] = "in"
ATTR_FRIENDLY_NAME: Final[str] = "fn"

# Power states.
BANGOLUFSEN_ON: Final[str] = "on"

VALID_MEDIA_TYPES: Final[tuple] = (
    BangOlufsenMediaType.FAVOURITE,
    BangOlufsenMediaType.DEEZER,
    BangOlufsenMediaType.RADIO,
    BangOlufsenMediaType.TTS,
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
            type=SourceTypeEnum("uriStreamer"),
        ),
        Source(
            id="bluetooth",
            is_enabled=True,
            is_playable=False,
            name="Bluetooth",
            type=SourceTypeEnum("bluetooth"),
        ),
        Source(
            id="spotify",
            is_enabled=True,
            is_playable=False,
            name="Spotify Connect",
            type=SourceTypeEnum("spotify"),
        ),
        Source(
            id="lineIn",
            is_enabled=True,
            is_playable=True,
            name="Line-In",
            type=SourceTypeEnum("lineIn"),
        ),
        Source(
            id="spdif",
            is_enabled=True,
            is_playable=True,
            name="Optical",
            type=SourceTypeEnum("spdif"),
        ),
        Source(
            id="netRadio",
            is_enabled=True,
            is_playable=True,
            name="B&O Radio",
            type=SourceTypeEnum("netRadio"),
        ),
        Source(
            id="deezer",
            is_enabled=True,
            is_playable=True,
            name="Deezer",
            type=SourceTypeEnum("deezer"),
        ),
        Source(
            id="tidalConnect",
            is_enabled=True,
            is_playable=True,
            name="Tidal Connect",
            type=SourceTypeEnum("tidalConnect"),
        ),
    ]
)


# Device trigger events
BANGOLUFSEN_EVENT: Final[str] = f"{DOMAIN}_event"
BANGOLUFSEN_WEBSOCKET_EVENT: Final[str] = f"{DOMAIN}_websocket_event"


CONNECTION_STATUS: Final[str] = "CONNECTION_STATUS"

# Misc.
NO_METADATA: Final[tuple] = (None, "", 0)


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
        self._name: str = self.entry.data[CONF_NAME]
        self._unique_id: str = cast(str, self.entry.unique_id)

        self._client: MozartClient = MozartClient(
            host=self._host, websocket_reconnect=True
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


class BangOlufsenEntity(Entity, BangOlufsenVariables):
    """Base Entity for BangOlufsen entities."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the object."""
        BangOlufsenVariables.__init__(self, entry)
        self._dispatchers: list = []

        self._attr_should_poll = False
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, self._unique_id)})
        self._attr_device_class = None
        self._attr_entity_category = None

    async def async_added_to_hass(self) -> None:
        """Turn on the dispatchers."""
        self._dispatchers = [
            async_dispatcher_connect(
                self.hass,
                f"{self._unique_id}_{CONNECTION_STATUS}",
                self._update_connection_state,
            )
        ]

    async def async_will_remove_from_hass(self) -> None:
        """Turn off the dispatchers."""
        for dispatcher in self._dispatchers:
            dispatcher()

    async def _update_connection_state(self, connection_state: bool) -> None:
        """Update entity connection state."""
        self._attr_available = connection_state

        self.async_write_ha_state()

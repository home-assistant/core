"""LinkPlay constants."""

from linkplay.consts import EqualizerMode, LoopMode, PlayingMode, PlayingStatus

from homeassistant.components.media_player import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
    RepeatMode,
)
from homeassistant.const import Platform

DOMAIN = "linkplay"
CONTROLLER = "controller"
BRIDGE_DISCOVERED = "bridge_discovered"
DISCOVERY_SCAN_INTERVAL = 300
PLATFORMS = [Platform.MEDIA_PLAYER]

STATE_MAP: dict[PlayingStatus, MediaPlayerState] = {
    PlayingStatus.STOPPED: MediaPlayerState.IDLE,
    PlayingStatus.PAUSED: MediaPlayerState.PAUSED,
    PlayingStatus.PLAYING: MediaPlayerState.PLAYING,
    PlayingStatus.LOADING: MediaPlayerState.BUFFERING,
}

SOURCE_MAP: dict[PlayingMode, str] = {
    PlayingMode.LINE_IN: "Line In",
    PlayingMode.BLUETOOTH: "Bluetooth",
    PlayingMode.OPTICAL: "Optical",
    PlayingMode.LINE_IN_2: "Line In 2",
    PlayingMode.USB_DAC: "USB DAC",
    PlayingMode.COAXIAL: "Coaxial",
    PlayingMode.XLR: "XLR",
    PlayingMode.HDMI: "HDMI",
    PlayingMode.OPTICAL_2: "Optical 2",
}

SOURCE_MAP_INV: dict[str, PlayingMode] = {v: k for k, v in SOURCE_MAP.items()}

REPEAT_MAP: dict[LoopMode, RepeatMode] = {
    LoopMode.CONTINOUS_PLAY_ONE_SONG: RepeatMode.ONE,
    LoopMode.PLAY_IN_ORDER: RepeatMode.OFF,
    LoopMode.CONTINUOUS_PLAYBACK: RepeatMode.ALL,
    LoopMode.RANDOM_PLAYBACK: RepeatMode.ALL,
    LoopMode.LIST_CYCLE: RepeatMode.ALL,
}

REPEAT_MAP_INV: dict[RepeatMode, LoopMode] = {v: k for k, v in REPEAT_MAP.items()}

EQUALIZER_MAP: dict[EqualizerMode, str] = {
    EqualizerMode.NONE: "None",
    EqualizerMode.CLASSIC: "Classic",
    EqualizerMode.POP: "Pop",
    EqualizerMode.JAZZ: "Jazz",
    EqualizerMode.VOCAL: "Vocal",
}

EQUALIZER_MAP_INV: dict[str, EqualizerMode] = {v: k for k, v in EQUALIZER_MAP.items()}

DEFAULT_FEATURES: MediaPlayerEntityFeature = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.BROWSE_MEDIA
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.GROUPING
)

SEEKABLE_FEATURES: MediaPlayerEntityFeature = (
    MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.REPEAT_SET
    | MediaPlayerEntityFeature.SEEK
)

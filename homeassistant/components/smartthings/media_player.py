"""Support for media players through the SmartThings cloud API."""

from __future__ import annotations

from typing import Any

from pysmartthings import Attribute, Capability, Category, Command, SmartThings

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    RepeatMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity

MEDIA_PLAYER_CAPABILITIES = (
    Capability.AUDIO_MUTE,
    Capability.AUDIO_VOLUME,
    Capability.MEDIA_PLAYBACK,
)

CONTROLLABLE_SOURCES = ["bluetooth", "wifi"]

DEVICE_CLASS_MAP: dict[Category | str, MediaPlayerDeviceClass] = {
    Category.NETWORK_AUDIO: MediaPlayerDeviceClass.SPEAKER,
    Category.SPEAKER: MediaPlayerDeviceClass.SPEAKER,
    Category.TELEVISION: MediaPlayerDeviceClass.TV,
    Category.RECEIVER: MediaPlayerDeviceClass.RECEIVER,
}

VALUE_TO_STATE = {
    "buffering": MediaPlayerState.BUFFERING,
    "paused": MediaPlayerState.PAUSED,
    "playing": MediaPlayerState.PLAYING,
    "stopped": MediaPlayerState.IDLE,
    "fast forwarding": MediaPlayerState.BUFFERING,
    "rewinding": MediaPlayerState.BUFFERING,
}

REPEAT_MODE_TO_HA = {
    "all": RepeatMode.ALL,
    "one": RepeatMode.ONE,
    "off": RepeatMode.OFF,
}

HA_REPEAT_MODE_TO_SMARTTHINGS = {v: k for k, v in REPEAT_MODE_TO_HA.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add media players for a config entry."""
    entry_data = entry.runtime_data

    async_add_entities(
        SmartThingsMediaPlayer(entry_data.client, device)
        for device in entry_data.devices.values()
        if all(
            capability in device.status[MAIN]
            for capability in MEDIA_PLAYER_CAPABILITIES
        )
    )


class SmartThingsMediaPlayer(SmartThingsEntity, MediaPlayerEntity):
    """Define a SmartThings media player."""

    _attr_name = None

    def __init__(self, client: SmartThings, device: FullDevice) -> None:
        """Initialize the media_player class."""
        super().__init__(
            client,
            device,
            {
                Capability.AUDIO_MUTE,
                Capability.AUDIO_TRACK_DATA,
                Capability.AUDIO_VOLUME,
                Capability.MEDIA_INPUT_SOURCE,
                Capability.MEDIA_PLAYBACK,
                Capability.MEDIA_PLAYBACK_REPEAT,
                Capability.MEDIA_PLAYBACK_SHUFFLE,
                Capability.SAMSUNG_VD_AUDIO_INPUT_SOURCE,
                Capability.SWITCH,
            },
        )
        self._attr_supported_features = self._determine_features()
        self._attr_device_class = DEVICE_CLASS_MAP.get(
            device.device.components[MAIN].user_category
            or device.device.components[MAIN].manufacturer_category,
        )

    def _determine_features(self) -> MediaPlayerEntityFeature:
        flags = MediaPlayerEntityFeature(0)
        playback_commands = self.get_attribute_value(
            Capability.MEDIA_PLAYBACK, Attribute.SUPPORTED_PLAYBACK_COMMANDS
        )
        if "play" in playback_commands:
            flags |= MediaPlayerEntityFeature.PLAY
        if "pause" in playback_commands:
            flags |= MediaPlayerEntityFeature.PAUSE
        if "stop" in playback_commands:
            flags |= MediaPlayerEntityFeature.STOP
        if "rewind" in playback_commands:
            flags |= MediaPlayerEntityFeature.PREVIOUS_TRACK
        if "fastForward" in playback_commands:
            flags |= MediaPlayerEntityFeature.NEXT_TRACK
        if self.supports_capability(Capability.AUDIO_VOLUME):
            flags |= (
                MediaPlayerEntityFeature.VOLUME_SET
                | MediaPlayerEntityFeature.VOLUME_STEP
            )
        if self.supports_capability(Capability.AUDIO_MUTE):
            flags |= MediaPlayerEntityFeature.VOLUME_MUTE
        if self.supports_capability(Capability.SWITCH):
            flags |= (
                MediaPlayerEntityFeature.TURN_ON | MediaPlayerEntityFeature.TURN_OFF
            )
        if self.supports_capability(Capability.MEDIA_INPUT_SOURCE):
            flags |= MediaPlayerEntityFeature.SELECT_SOURCE
        if self.supports_capability(Capability.MEDIA_PLAYBACK_SHUFFLE):
            flags |= MediaPlayerEntityFeature.SHUFFLE_SET
        if self.supports_capability(Capability.MEDIA_PLAYBACK_REPEAT):
            flags |= MediaPlayerEntityFeature.REPEAT_SET
        return flags

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the media player off."""
        await self.execute_device_command(
            Capability.SWITCH,
            Command.OFF,
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the media player on."""
        await self.execute_device_command(
            Capability.SWITCH,
            Command.ON,
        )

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute volume."""
        await self.execute_device_command(
            Capability.AUDIO_MUTE,
            Command.SET_MUTE,
            argument="muted" if mute else "unmuted",
        )

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        await self.execute_device_command(
            Capability.AUDIO_VOLUME,
            Command.SET_VOLUME,
            argument=int(volume * 100),
        )

    async def async_volume_up(self) -> None:
        """Increase volume."""
        await self.execute_device_command(
            Capability.AUDIO_VOLUME,
            Command.VOLUME_UP,
        )

    async def async_volume_down(self) -> None:
        """Decrease volume."""
        await self.execute_device_command(
            Capability.AUDIO_VOLUME,
            Command.VOLUME_DOWN,
        )

    async def async_media_play(self) -> None:
        """Play media."""
        await self.execute_device_command(
            Capability.MEDIA_PLAYBACK,
            Command.PLAY,
        )

    async def async_media_pause(self) -> None:
        """Pause media."""
        await self.execute_device_command(
            Capability.MEDIA_PLAYBACK,
            Command.PAUSE,
        )

    async def async_media_stop(self) -> None:
        """Stop media."""
        await self.execute_device_command(
            Capability.MEDIA_PLAYBACK,
            Command.STOP,
        )

    async def async_media_previous_track(self) -> None:
        """Previous track."""
        await self.execute_device_command(
            Capability.MEDIA_PLAYBACK,
            Command.REWIND,
        )

    async def async_media_next_track(self) -> None:
        """Next track."""
        await self.execute_device_command(
            Capability.MEDIA_PLAYBACK,
            Command.FAST_FORWARD,
        )

    async def async_select_source(self, source: str) -> None:
        """Select source."""
        await self.execute_device_command(
            Capability.MEDIA_INPUT_SOURCE,
            Command.SET_INPUT_SOURCE,
            argument=source,
        )

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Set shuffle mode."""
        await self.execute_device_command(
            Capability.MEDIA_PLAYBACK_SHUFFLE,
            Command.SET_PLAYBACK_SHUFFLE,
            argument="enabled" if shuffle else "disabled",
        )

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        await self.execute_device_command(
            Capability.MEDIA_PLAYBACK_REPEAT,
            Command.SET_PLAYBACK_REPEAT_MODE,
            argument=HA_REPEAT_MODE_TO_SMARTTHINGS[repeat],
        )

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        if (
            not self.supports_capability(Capability.AUDIO_TRACK_DATA)
            or (
                track_data := self.get_attribute_value(
                    Capability.AUDIO_TRACK_DATA, Attribute.AUDIO_TRACK_DATA
                )
            )
            is None
        ):
            return None
        return track_data.get("title", None)

    @property
    def media_artist(self) -> str | None:
        """Artist of current playing media."""
        if (
            not self.supports_capability(Capability.AUDIO_TRACK_DATA)
            or (
                track_data := self.get_attribute_value(
                    Capability.AUDIO_TRACK_DATA, Attribute.AUDIO_TRACK_DATA
                )
            )
            is None
        ):
            return None
        return track_data.get("artist")

    @property
    def state(self) -> MediaPlayerState | None:
        """State of the media player."""
        if self.supports_capability(Capability.SWITCH):
            if self.get_attribute_value(Capability.SWITCH, Attribute.SWITCH) == "on":
                if (
                    self.source is not None
                    and self.source in CONTROLLABLE_SOURCES
                    and self.get_attribute_value(
                        Capability.MEDIA_PLAYBACK, Attribute.PLAYBACK_STATUS
                    )
                    in VALUE_TO_STATE
                ):
                    return VALUE_TO_STATE[
                        self.get_attribute_value(
                            Capability.MEDIA_PLAYBACK, Attribute.PLAYBACK_STATUS
                        )
                    ]
                return MediaPlayerState.ON
            return MediaPlayerState.OFF
        return VALUE_TO_STATE[
            self.get_attribute_value(
                Capability.MEDIA_PLAYBACK, Attribute.PLAYBACK_STATUS
            )
        ]

    @property
    def is_volume_muted(self) -> bool:
        """Returns if the volume is muted."""
        return (
            self.get_attribute_value(Capability.AUDIO_MUTE, Attribute.MUTE) == "muted"
        )

    @property
    def volume_level(self) -> float:
        """Volume level."""
        return self.get_attribute_value(Capability.AUDIO_VOLUME, Attribute.VOLUME) / 100

    @property
    def source(self) -> str | None:
        """Input source."""
        if self.supports_capability(Capability.MEDIA_INPUT_SOURCE):
            return self.get_attribute_value(
                Capability.MEDIA_INPUT_SOURCE, Attribute.INPUT_SOURCE
            )
        if self.supports_capability(Capability.SAMSUNG_VD_AUDIO_INPUT_SOURCE):
            return self.get_attribute_value(
                Capability.SAMSUNG_VD_AUDIO_INPUT_SOURCE, Attribute.INPUT_SOURCE
            )
        return None

    @property
    def source_list(self) -> list[str] | None:
        """List of input sources."""
        if self.supports_capability(Capability.MEDIA_INPUT_SOURCE):
            return self.get_attribute_value(
                Capability.MEDIA_INPUT_SOURCE, Attribute.SUPPORTED_INPUT_SOURCES
            )
        if self.supports_capability(Capability.SAMSUNG_VD_AUDIO_INPUT_SOURCE):
            return self.get_attribute_value(
                Capability.SAMSUNG_VD_AUDIO_INPUT_SOURCE,
                Attribute.SUPPORTED_INPUT_SOURCES,
            )
        return None

    @property
    def shuffle(self) -> bool | None:
        """Returns if shuffle mode is set."""
        if self.supports_capability(Capability.MEDIA_PLAYBACK_SHUFFLE):
            return (
                self.get_attribute_value(
                    Capability.MEDIA_PLAYBACK_SHUFFLE, Attribute.PLAYBACK_SHUFFLE
                )
                == "enabled"
            )
        return None

    @property
    def repeat(self) -> RepeatMode | None:
        """Returns if repeat mode is set."""
        if self.supports_capability(Capability.MEDIA_PLAYBACK_REPEAT):
            return REPEAT_MODE_TO_HA[
                self.get_attribute_value(
                    Capability.MEDIA_PLAYBACK_REPEAT, Attribute.PLAYBACK_REPEAT_MODE
                )
            ]
        return None

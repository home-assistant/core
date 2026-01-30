"""Media Player Entities for Lyngdorf Integration."""

from __future__ import annotations

from datetime import timedelta
from typing import cast

from lyngdorf.device import Receiver

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .config_flow import DOMAIN
from .const import (
    CONF_DEVICE_INFO,
    CONF_RECEIVER,
    FEATURES_MP60,
    FEATURES_MP60_ZONE_B,
    NAME_MAIN_ZONE,
    NAME_ZONE_B,
)

ATTR_AUDIO_INFO = "audio_info"
ATTR_VIDEO_INFO = "video_info"
ATTR_AUDIO_INPUT = "audio_input"
ATTR_VIDEO_INPUT = "video_input"
ATTR_STREAMING_SOURCE = "streaming_source"
ATTR_ROOM_PERFECT_POSITION = "room_perfect_position"
ATTR_ROOM_PERFECT_POSITION_LIST = "room_perfect_position_list"

SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 1


class MP60Device(MediaPlayerEntity):
    """Basic MP60Device."""

    def __init__(
        self,
        receiver: Receiver,
        config_entry: ConfigEntry,
        device_info: DeviceInfo,
        name: str,
        id: str,
        features: MediaPlayerEntityFeature = MediaPlayerEntityFeature(0),
    ) -> None:
        """Initialize the device."""
        assert config_entry.unique_id
        self._attr_has_entity_name = True
        self._attr_device_info = device_info
        self._attr_unique_id = f"{config_entry.unique_id}_{id}"
        self._receiver = receiver
        self._attr_device_class = MediaPlayerDeviceClass.RECEIVER
        self._attr_name = name
        self._attr_supported_features = features

    async def async_added_to_hass(self) -> None:
        """Notfies us that haas has started."""
        self._receiver.register_notification_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Notfies us that haas is stopping."""
        self._receiver.un_register_notification_callback(self.async_write_ha_state)


class MP60ZoneBDevice(MP60Device):
    """MP60 Zone B."""

    def __init__(
        self, receiver: Receiver, config_entry: ConfigEntry, device_info: DeviceInfo
    ) -> None:
        """Create the device."""
        MP60Device.__init__(
            self,
            receiver,
            config_entry,
            device_info,
            NAME_ZONE_B,
            "zone_b",
            FEATURES_MP60_ZONE_B,
        )

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if self._receiver.zone_b_power_on:
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self._receiver.zone_b_mute_enabled

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        # Volume is sent in a format like -50.0. Minimum is -80.0,
        # maximum is 18.0
        if self._receiver.zone_b_volume is None or not isinstance(
            self._receiver.zone_b_volume, float
        ):
            return None
        return (float(self._receiver.zone_b_volume) + 80) / 100

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        state_attributes = {}
        if self._receiver.zone_b_audio_input is not None:
            state_attributes[ATTR_AUDIO_INPUT] = self._receiver.zone_b_audio_input
        if self._receiver.zone_b_streaming_source is not None:
            state_attributes[ATTR_STREAMING_SOURCE] = (
                self._receiver.zone_b_streaming_source
            )

        return state_attributes

    def turn_on(self) -> None:
        """Turn on media player."""
        self._receiver.zone_b_power_on = True

    def turn_off(self) -> None:
        """Turn off media player."""
        self._receiver.zone_b_power_on = False

    def volume_up(self) -> None:
        """Volume up the media player."""
        self._receiver.zone_b_volume_up()

    def volume_down(self) -> None:
        """Volume down the media player."""
        self._receiver.zone_b_volume_down()

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        # Volume has to be sent in a format like -50.0. Minimum is -80.0,
        # maximum is 18.0
        volume_lyngdorf = float((volume * 100) - 80)
        if volume_lyngdorf > 18:
            volume_lyngdorf = float(18)
        self._receiver.zone_b_volume = volume_lyngdorf

    def mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        self._receiver.zone_b_mute_enabled = mute

    @property
    def source(self) -> str | None:
        """Name of the current input source."""
        return self._receiver.zone_b_source

    @property
    def source_list(self) -> list[str] | None:
        """The list of available sources."""
        return self._receiver.zone_b_available_sources

    def select_source(self, source: str) -> None:
        """Select input source."""
        self._receiver.zone_b_source = source


class MP60MainDevice(MP60Device):
    """MP60 Main Device."""

    def __init__(
        self, receiver: Receiver, config_entry: ConfigEntry, device_info: DeviceInfo
    ) -> None:
        """Create the device."""
        MP60Device.__init__(
            self,
            receiver,
            config_entry,
            device_info,
            NAME_MAIN_ZONE,
            "main_zone",
            FEATURES_MP60,
        )

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the device."""
        if self._receiver.power_on:
            if self._playing_audio or self._playing_video:
                return MediaPlayerState.PLAYING
            return MediaPlayerState.ON
        return MediaPlayerState.OFF

    @property
    def media_title(self) -> str | None:
        """Title of the Media. Describes the media being played in our case."""
        response: str = ""
        if self.state == MediaPlayerState.PLAYING:
            if self._playing_audio:
                response = f"audio: {self._receiver.audio_information} "
            if self._playing_video:
                response = f"{response}video: {self._receiver.video_information}"
            return response
        return None

    @property
    def _playing_video(self):
        """Video Playing."""
        return (
            self._receiver.video_information is not None
            and len(self._receiver.video_information) > 0
            and not self._receiver.video_information.startswith("No")
        )

    @property
    def _playing_audio(self):
        """Audio Playing."""
        return (
            self._receiver.audio_information is not None
            and len(self._receiver.audio_information) > 0
            and not self._receiver.audio_information.startswith("No")
        )

    @property
    def media_content_type(self):
        """Video or Audio playing."""
        if self.state == MediaPlayerState.PLAYING:
            if (
                self._receiver.video_information is not None
                and len(self._receiver.video_information) > 0
            ):
                return MediaType.VIDEO
            return MediaType.MUSIC
        return None

    @property
    def source_list(self):
        """Return a list of available input sources."""
        return self._receiver.available_sources

    @property
    def sound_mode_list(self):
        """Return a list of available input sources."""
        return self._receiver.available_sound_modes

    @property
    def is_volume_muted(self):
        """Return boolean if volume is currently muted."""
        return self._receiver.mute_enabled

    @property
    def volume_level(self):
        """Volume level of the media player (0..1)."""
        # Volume is sent in a format like -50.0. Minimum is -80.0,
        # maximum is 18.0
        if self._receiver.volume is None or not isinstance(
            self._receiver.volume, float
        ):
            return None
        return (float(self._receiver.volume) + 80) / 100

    @property
    def source(self):
        """Return the current input source."""
        return self._receiver.source

    @property
    def sound_mode(self):
        """Return the current matched sound mode."""
        return self._receiver.sound_mode

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        state_attributes = {}
        if self._receiver.audio_information is not None:
            state_attributes[ATTR_AUDIO_INFO] = self._receiver.audio_information
        if self._receiver.video_information is not None:
            state_attributes[ATTR_VIDEO_INFO] = self._receiver.video_information
        if self._receiver.audio_input is not None:
            state_attributes[ATTR_AUDIO_INPUT] = self._receiver.audio_input
        if self._receiver.video_input is not None:
            state_attributes[ATTR_VIDEO_INPUT] = self._receiver.video_input
        if self._receiver.streaming_source is not None:
            state_attributes[ATTR_STREAMING_SOURCE] = self._receiver.streaming_source
        if self._receiver.room_perfect_position is not None:
            state_attributes[ATTR_ROOM_PERFECT_POSITION] = (
                self._receiver.room_perfect_position
            )
        if self._receiver.available_room_perfect_positions is not None:
            state_attributes[ATTR_ROOM_PERFECT_POSITION_LIST] = (
                self._receiver.available_room_perfect_positions
            )

        return state_attributes

    def turn_on(self) -> None:
        """Turn on media player."""
        self._receiver.power_on = True

    def turn_off(self) -> None:
        """Turn off media player."""
        self._receiver.power_on = False

    def volume_up(self) -> None:
        """Volume up the media player."""
        self._receiver.volume_up()

    def volume_down(self) -> None:
        """Volume down the media player."""
        self._receiver.volume_down()

    def set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        # Volume has to be sent in a format like -50.0. Minimum is -80.0,
        # maximum is 18.0
        volume_lyngdorf = float((volume * 100) - 80)
        if volume_lyngdorf > 18:
            volume_lyngdorf = float(18)
        self._receiver.volume = volume_lyngdorf

    def mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        self._receiver.mute_enabled = mute

    def select_sound_mode(self, sound_mode: str) -> None:
        """Select sound mode."""
        self._receiver.sound_mode = sound_mode

    def select_source(self, source: str) -> None:
        """Select input source."""
        self._receiver.source = source

    def select_room_perfect_position(self, room_perfect_position: str) -> None:
        """Select input source."""
        self._receiver.room_perfect_position = room_perfect_position


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the receiver from a config entry."""
    entities = []
    data = hass.data[DOMAIN][config_entry.entry_id]
    client: Receiver = data[CONF_RECEIVER]
    device_info: DeviceInfo = data[CONF_DEVICE_INFO]

    entities.append(cast(Entity, MP60MainDevice(client, config_entry, device_info)))
    entities.append(cast(Entity, MP60ZoneBDevice(client, config_entry, device_info)))

    async_add_entities(entities)

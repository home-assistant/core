"""Matter media player platform."""

from collections import Counter
from dataclasses import dataclass
from typing import override

from chip.clusters import Objects as clusters
from chip.clusters.ClusterObjects import ClusterCommand
from chip.clusters.Types import NullValue
from matter_server.client.models import device_types

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MATTER_2000_TO_UNIX_EPOCH_OFFSET
from .entity import MatterEntity, MatterEntityDescription
from .helpers import MatterConfigEntry
from .models import MatterDiscoverySchema

STATE_WRITE_DEBOUNCE_COOLDOWN = 0.1

PlaybackState = clusters.MediaPlayback.Enums.PlaybackStateEnum
PlaybackStatus = clusters.MediaPlayback.Enums.StatusEnum
PlaybackCommands = clusters.MediaPlayback.Commands

PLAYBACK_STATE_MAP = {
    PlaybackState.kPlaying: MediaPlayerState.PLAYING,
    PlaybackState.kPaused: MediaPlayerState.PAUSED,
    PlaybackState.kNotPlaying: MediaPlayerState.IDLE,
    PlaybackState.kBuffering: MediaPlayerState.BUFFERING,
}

# Translation keys for the PlaybackResponse statuses that are not success
PLAYBACK_STATUS_ERRORS = {
    PlaybackStatus.kInvalidStateForCommand: "media_playback_invalid_state",
    PlaybackStatus.kNotAllowed: "media_playback_not_allowed",
    PlaybackStatus.kNotActive: "media_playback_not_active",
    PlaybackStatus.kSpeedOutOfRange: "media_playback_speed_out_of_range",
    PlaybackStatus.kSeekOutOfRange: "media_playback_seek_out_of_range",
}

# Optional Media Playback commands, supported when in the AcceptedCommandList
OPTIONAL_PLAYBACK_COMMANDS = {
    PlaybackCommands.Previous.command_id: MediaPlayerEntityFeature.PREVIOUS_TRACK,
    PlaybackCommands.Next.command_id: MediaPlayerEntityFeature.NEXT_TRACK,
    PlaybackCommands.Seek.command_id: MediaPlayerEntityFeature.SEEK,
}


def source_names(
    inputs: list[clusters.MediaInput.Structs.InputInfoStruct],
) -> dict[int, str]:
    """Return a unique source name per input index.

    Duplicate names get their input index. If that still collides with another
    input's name, all names get their index, which is unique by itself.
    """
    name_counts = Counter(x.name for x in inputs)
    names = {
        x.index: x.name if name_counts[x.name] == 1 else f"{x.name} ({x.index})"
        for x in inputs
    }
    if len(set(names.values())) < len(names):
        return {x.index: f"{x.name} ({x.index})" for x in inputs}
    return names


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MatterConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Matter media players from Config Entry."""
    matter = config_entry.runtime_data.adapter
    matter.register_platform_handler(Platform.MEDIA_PLAYER, async_add_entities)


@dataclass(frozen=True, kw_only=True)
class MatterMediaPlayerEntityDescription(
    MediaPlayerEntityDescription, MatterEntityDescription
):
    """Describe Matter media player entities."""


class MatterMediaPlayer(MatterEntity, MediaPlayerEntity):
    """Representation of a Matter video player."""

    entity_description: MatterMediaPlayerEntityDescription
    _write_state_debounce_cooldown = STATE_WRITE_DEBOUNCE_COOLDOWN
    _last_on_off_feature_map: int | None = None
    _last_accepted_commands: list[int] | None = None
    _last_has_inputs: bool | None = None

    @override
    async def async_turn_on(self) -> None:
        """Turn the video player on."""
        await self.send_device_command(clusters.OnOff.Commands.On())

    @override
    async def async_turn_off(self) -> None:
        """Turn the video player off."""
        await self.send_device_command(clusters.OnOff.Commands.Off())

    @override
    async def async_media_play(self) -> None:
        """Start or resume playback."""
        await self._send_playback_command(PlaybackCommands.Play())

    @override
    async def async_media_pause(self) -> None:
        """Pause playback."""
        await self._send_playback_command(PlaybackCommands.Pause())

    @override
    async def async_media_stop(self) -> None:
        """Stop playback."""
        await self._send_playback_command(PlaybackCommands.Stop())

    @override
    async def async_media_previous_track(self) -> None:
        """Go to the previous media item."""
        await self._send_playback_command(PlaybackCommands.Previous())

    @override
    async def async_media_next_track(self) -> None:
        """Go to the next media item."""
        await self._send_playback_command(PlaybackCommands.Next())

    @override
    async def async_media_seek(self, position: float) -> None:
        """Seek to a position, in seconds."""
        await self._send_playback_command(
            PlaybackCommands.Seek(position=round(position * 1000))
        )

    @override
    async def async_select_source(self, source: str) -> None:
        """Switch to the given input."""
        inputs: list[clusters.MediaInput.Structs.InputInfoStruct] = (
            self.get_matter_attribute_value(clusters.MediaInput.Attributes.InputList)
        )
        index = next(
            (index for index, name in source_names(inputs).items() if name == source),
            None,
        )
        if index is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_media_input",
                translation_placeholders={"source": source},
            )
        await self.send_device_command(
            clusters.MediaInput.Commands.SelectInput(index=index)
        )

    async def _send_playback_command(self, command: ClusterCommand) -> None:
        """Send a Media Playback command and check its PlaybackResponse."""
        response = await self.send_device_command(command)
        status = response["status"]
        if status == PlaybackStatus.kSuccess:
            return
        placeholders = None
        if (translation_key := PLAYBACK_STATUS_ERRORS.get(status)) is None:
            translation_key = "media_playback_failed"
            placeholders = {"status": str(status)}
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders=placeholders,
        )

    @callback
    @override
    def _update_from_device(self) -> None:
        """Update from device."""
        if not self.get_matter_attribute_value(clusters.OnOff.Attributes.OnOff):
            self._attr_state = MediaPlayerState.OFF
        else:
            self._attr_state = PLAYBACK_STATE_MAP.get(
                self.get_matter_attribute_value(
                    clusters.MediaPlayback.Attributes.CurrentState
                ),
                MediaPlayerState.ON,
            )
        self._calculate_features()
        self._update_position()
        self._update_sources()

    @callback
    def _calculate_features(self) -> None:
        """Calculate features for HA MediaPlayer platform."""
        on_off_feature_map: int = (
            self.get_matter_attribute_value(clusters.OnOff.Attributes.FeatureMap) or 0
        )
        accepted_commands: list[int] = (
            self.get_matter_attribute_value(
                clusters.MediaPlayback.Attributes.AcceptedCommandList
            )
            or []
        )
        has_inputs = bool(
            self.get_matter_attribute_value(clusters.MediaInput.Attributes.InputList)
        )

        # In principle the feature set should not change, except for the
        # On/Off feature map, accepted commands and available inputs.
        if (
            self._last_on_off_feature_map == on_off_feature_map
            and self._last_accepted_commands == accepted_commands
            and self._last_has_inputs == has_inputs
        ):
            return

        self._last_on_off_feature_map = on_off_feature_map
        self._last_accepted_commands = accepted_commands
        self._last_has_inputs = has_inputs
        features = (
            MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
        )
        if not on_off_feature_map & clusters.OnOff.Bitmaps.Feature.kOffOnly:
            features |= MediaPlayerEntityFeature.TURN_ON
        for command_id, feature in OPTIONAL_PLAYBACK_COMMANDS.items():
            if command_id in accepted_commands:
                features |= feature
        if has_inputs:
            features |= MediaPlayerEntityFeature.SELECT_SOURCE
        self._attr_supported_features = features

    @callback
    def _update_position(self) -> None:
        """Update the playback position and duration (AdvancedSeek feature)."""
        duration = self.get_matter_attribute_value(
            clusters.MediaPlayback.Attributes.Duration
        )
        self._attr_media_duration = duration / 1000 if duration is not None else None

        sampled: clusters.MediaPlayback.Structs.PlaybackPositionStruct | None = (
            self.get_matter_attribute_value(
                clusters.MediaPlayback.Attributes.SampledPosition
            )
        )
        if (
            sampled is None
            or sampled.updatedAt == 0
            or sampled.position in (None, NullValue)
        ):
            self._attr_media_position = None
            self._attr_media_position_updated_at = None
            return
        self._attr_media_position = sampled.position / 1000
        self._attr_media_position_updated_at = dt_util.utc_from_timestamp(
            sampled.updatedAt / 1_000_000 + MATTER_2000_TO_UNIX_EPOCH_OFFSET
        )

    @callback
    def _update_sources(self) -> None:
        """Update the input list and current input."""
        inputs: list[clusters.MediaInput.Structs.InputInfoStruct] = (
            self.get_matter_attribute_value(clusters.MediaInput.Attributes.InputList)
            or []
        )
        names = source_names(inputs)
        self._attr_source_list = list(names.values()) or None
        self._attr_source = names.get(
            self.get_matter_attribute_value(clusters.MediaInput.Attributes.CurrentInput)
        )


# Discovery schema(s) to map Matter Attributes to HA entities
DISCOVERY_SCHEMAS = [
    MatterDiscoverySchema(
        platform=Platform.MEDIA_PLAYER,
        entity_description=MatterMediaPlayerEntityDescription(
            key="MatterBasicVideoPlayer",
            name=None,
        ),
        entity_class=MatterMediaPlayer,
        required_attributes=(
            clusters.OnOff.Attributes.OnOff,
            clusters.MediaPlayback.Attributes.CurrentState,
        ),
        optional_attributes=(
            clusters.OnOff.Attributes.FeatureMap,
            clusters.MediaPlayback.Attributes.AcceptedCommandList,
            clusters.MediaPlayback.Attributes.Duration,
            clusters.MediaPlayback.Attributes.SampledPosition,
            clusters.MediaInput.Attributes.InputList,
            clusters.MediaInput.Attributes.CurrentInput,
        ),
        device_type=(device_types.BasicVideoPlayer,),
    ),
]

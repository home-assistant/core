"""Media player entity for Arcam Solo."""

from pyarcamsolo.commands import SOURCE_SELECTION_CODES

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ArcamSoloConfigEntry
from .const import (
    CD_STATE_MAP,
    MAX_VOLUME,
    MUSIC_SOURCES,
    NAVIGATION_SOURCES,
    PLAYABLE_SOURCES,
    TRACK_SOURCES,
)
from .entity import ArcamSoloEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ArcamSoloConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Arcam Solo media player platform."""
    async_add_entities([ArcamSoloMediaPlayerEntity(entry)])


class ArcamSoloMediaPlayerEntity(MediaPlayerEntity, ArcamSoloEntity):
    """Media player entity for Arcam Solo."""

    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: ArcamSoloConfigEntry) -> None:
        """Initialize the media player entity."""
        super().__init__(entry, "media_player")

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the state of the media player."""
        zone_state = self.arcam_solo.zones.get(1)
        if zone_state is None or "power" not in zone_state:
            return None
        if zone_state["power"] == "Standby":
            return MediaPlayerState.OFF
        if self.source == "CD":
            cd_state = zone_state.get("cd_playback_state")
            if cd_state in CD_STATE_MAP:
                return CD_STATE_MAP[cd_state]
        return MediaPlayerState.ON

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.arcam_solo.available and 1 in self.arcam_solo.zones

    @property
    def source(self) -> str | None:
        """Return the currently selected source."""
        return self.arcam_solo.source

    @property
    def volume_level(self) -> float | None:
        """Volume level between 0 and 1."""
        volume = self.arcam_solo.zones.get(1, {}).get("volume")
        return volume / MAX_VOLUME if volume is not None else None

    @property
    def is_volume_muted(self) -> bool:
        """Return if volume is muted."""
        return self.arcam_solo.zones.get(1, {}).get("muted", False)

    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Return supported features for this platform."""
        features = (
            MediaPlayerEntityFeature.TURN_OFF
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.VOLUME_MUTE
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.SELECT_SOURCE
        )
        if self.source in PLAYABLE_SOURCES:
            features |= (
                MediaPlayerEntityFeature.PLAY
                | MediaPlayerEntityFeature.PAUSE
                | MediaPlayerEntityFeature.STOP
                | MediaPlayerEntityFeature.REPEAT_SET
                | MediaPlayerEntityFeature.SHUFFLE_SET
            )
        if self.source in TRACK_SOURCES:
            features |= (
                MediaPlayerEntityFeature.NEXT_TRACK
                | MediaPlayerEntityFeature.PREVIOUS_TRACK
            )
        return features

    @property
    def source_list(self) -> list[str]:
        """Return all available sources."""
        return [source for source in SOURCE_SELECTION_CODES.values() if source != "N/A"]

    @property
    def media_title(self) -> str | None:
        """Title of current playing media."""
        zone_state = self.arcam_solo.zones.get(1, {})
        if self.source == "DAB":
            return zone_state.get("radio_station")
        if self.source in PLAYABLE_SOURCES:
            if zone_state.get("cd_playback_state") in ("Playing", "Paused"):
                return f"Track {self.media_track} / {self.media_total_tracks}"
            return zone_state.get("cd_playback_state", self.source)
        return self.source

    @property
    def media_position(self) -> int | None:
        """Position of media currently playing in seconds."""
        if self.source in PLAYABLE_SOURCES:
            return self.arcam_solo.zones.get(1, {}).get("current_track_position")
        return None

    @property
    def media_track(self) -> int | None:
        """Return the current track."""
        if self.source in PLAYABLE_SOURCES:
            return self.arcam_solo.zones.get(1, {}).get("lsb_current_track")
        return None

    @property
    def media_total_tracks(self) -> int | None:
        """Return the total number of tracks."""
        if self.source in PLAYABLE_SOURCES:
            return self.arcam_solo.zones.get(1, {}).get("lsb_total_track")
        return None

    @property
    def media_duration(self) -> int | None:
        """Total duration of media currently playing in seconds."""
        return None

    @property
    def repeat(self) -> RepeatMode | None:
        """Return current repeat mode."""
        if self.source not in PLAYABLE_SOURCES:
            return None
        value = self.arcam_solo.zones.get(1, {}).get("repeat")
        if value == "all":
            return RepeatMode.ALL
        if value == "single":
            return RepeatMode.ONE
        return RepeatMode.OFF

    @property
    def shuffle(self) -> bool | None:
        """Return shuffle mode."""
        if self.source in PLAYABLE_SOURCES:
            return self.arcam_solo.zones.get(1, {}).get("shuffle", False)
        return None

    @property
    def media_type(self) -> MediaType | None:
        """Return the current media type."""
        if self.source not in MUSIC_SOURCES:
            return None
        if self.source in NAVIGATION_SOURCES:
            return MediaType.MUSIC
        if self.state in (
            MediaPlayerState.PLAYING,
            MediaPlayerState.PAUSED,
            MediaPlayerState.BUFFERING,
        ):
            return MediaType.MUSIC
        return None

    async def async_turn_on(self) -> None:
        """Turn the player on."""
        await self.arcam_solo.turn_on()

    async def async_turn_off(self) -> None:
        """Turn the player off."""
        await self.arcam_solo.turn_off()

    async def async_select_source(self, source: str) -> None:
        """Select input source."""
        await self.arcam_solo.set_source(source)

    async def async_volume_up(self) -> None:
        """Volume up media player."""
        await self.arcam_solo.send_ir_command(command="volume_plus")

    async def async_volume_down(self) -> None:
        """Volume down media player."""
        await self.arcam_solo.send_ir_command(command="volume_minus")

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level."""
        await self.arcam_solo.set_volume(round(volume * MAX_VOLUME))

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute media player."""
        await self.arcam_solo.send_ir_command(command="mute_on" if mute else "mute_off")

    async def async_media_play(self) -> None:
        """Send play command."""
        if self.source not in PLAYABLE_SOURCES:
            raise ServiceValidationError("Current source does not support this action")
        await self.arcam_solo.send_ir_command(command="cd_play")

    async def async_media_pause(self) -> None:
        """Send pause command."""
        if self.source not in PLAYABLE_SOURCES:
            raise ServiceValidationError("Current source does not support this action")
        await self.arcam_solo.send_ir_command(command="cd_pause")

    async def async_media_stop(self) -> None:
        """Send stop command."""
        if self.source not in PLAYABLE_SOURCES:
            raise ServiceValidationError("Current source does not support this action")
        await self.arcam_solo.send_ir_command(command="cd_stop")

    async def async_media_previous_track(self) -> None:
        """Send previous track command."""
        if self.source not in TRACK_SOURCES:
            raise ServiceValidationError("Current source does not support this action")
        if self.source in NAVIGATION_SOURCES:
            await self.arcam_solo.send_ir_command(command="navigate_down")
            return
        await self.arcam_solo.send_ir_command(command="cd_track_previous")

    async def async_media_next_track(self) -> None:
        """Send next track command."""
        if self.source not in TRACK_SOURCES:
            raise ServiceValidationError("Current source does not support this action")
        if self.source in NAVIGATION_SOURCES:
            await self.arcam_solo.send_ir_command(command="navigate_up")
            return
        await self.arcam_solo.send_ir_command(command="cd_track_next")

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        """Set repeat mode."""
        if repeat == RepeatMode.ALL:
            await self.arcam_solo.send_ir_command(command="cd_repeat_all")
        elif repeat == RepeatMode.ONE:
            await self.arcam_solo.send_ir_command(command="cd_repeat_single")
        elif repeat == RepeatMode.OFF:
            await self.arcam_solo.send_ir_command(command="cd_repeat_off")

    async def async_set_shuffle(self, shuffle: bool) -> None:
        """Set shuffle mode."""
        await self.arcam_solo.send_ir_command(
            command="cd_shuffle_on" if shuffle else "cd_shuffle_off"
        )

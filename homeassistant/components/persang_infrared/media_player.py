"""Media player platform for the Persang Infrared integration."""

from dataclasses import dataclass
from typing import Any, override

from infrared_protocols.codes.persang.speaker import PersangSpeakerCode

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from .const import CONF_INFRARED_EMITTER_ENTITY_ID
from .entity import PersangIrEntity

PARALLEL_UPDATES = 1

RESTORED_STATES = (
    MediaPlayerState.ON,
    MediaPlayerState.OFF,
    MediaPlayerState.PLAYING,
    MediaPlayerState.PAUSED,
)

# States in which the speaker is assumed to be powered on. The remote only has a
# power toggle, so turning on while already on would switch the speaker off.
ON_STATES = (
    MediaPlayerState.ON,
    MediaPlayerState.PLAYING,
    MediaPlayerState.PAUSED,
)


@dataclass
class _PersangSpeakerExtraData(ExtraStoredData):
    """Persisted assumed-state data for a Persang speaker.

    Stored separately from the entity state because while the speaker is OFF,
    ``MediaPlayerEntity.state_attributes`` strips mute, so a restart in the OFF
    state would otherwise lose it.
    """

    is_volume_muted: bool | None

    @override
    def as_dict(self) -> dict[str, Any]:
        """Serialize for the restore-state store."""
        return {"is_volume_muted": self.is_volume_muted}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Persang IR media player from a config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    async_add_entities([PersangIrMediaPlayer(entry, infrared_entity_id)])


class PersangIrMediaPlayer(PersangIrEntity, MediaPlayerEntity, RestoreEntity):
    """Persang IR speaker media player entity."""

    _attr_name = None
    _attr_assumed_state = True
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
    )

    def __init__(self, entry: ConfigEntry, infrared_entity_id: str) -> None:
        """Initialize the Persang IR media player."""
        super().__init__(entry, infrared_entity_id, unique_id_suffix="media_player")

    @property
    @override
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Persist mute regardless of the ON/OFF state."""
        return _PersangSpeakerExtraData(is_volume_muted=self._attr_is_volume_muted)

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last assumed state and mute."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None and (
            last_state.state in RESTORED_STATES
        ):
            self._attr_state = MediaPlayerState(last_state.state)

        if (extra := await self.async_get_last_extra_data()) is not None and (
            muted := extra.as_dict().get("is_volume_muted")
        ) is not None:
            self._attr_is_volume_muted = bool(muted)

    @override
    async def async_turn_on(self) -> None:
        """Send the power toggle unless the speaker is already assumed to be on."""
        if self._attr_state in ON_STATES:
            return

        await self._send_command(PersangSpeakerCode.POWER.to_command())
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    @override
    async def async_turn_off(self) -> None:
        """Send the power toggle unless the speaker is already assumed to be off."""
        if self._attr_state == MediaPlayerState.OFF:
            return

        await self._send_command(PersangSpeakerCode.POWER.to_command())
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    @override
    async def async_volume_up(self) -> None:
        """Send the volume up command."""
        await self._send_command(PersangSpeakerCode.VOLUME_UP.to_command())

    @override
    async def async_volume_down(self) -> None:
        """Send the volume down command."""
        await self._send_command(PersangSpeakerCode.VOLUME_DOWN.to_command())

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Send the mute toggle unless mute is already at the requested value."""
        if self._attr_is_volume_muted == mute:
            return

        await self._send_command(PersangSpeakerCode.MUTE.to_command())
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    @override
    async def async_media_play(self) -> None:
        """Send the play/pause toggle unless playback is already assumed to run."""
        if self._attr_state == MediaPlayerState.PLAYING:
            return

        await self._send_command(PersangSpeakerCode.PLAY_PAUSE.to_command())
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    @override
    async def async_media_pause(self) -> None:
        """Send the play/pause toggle unless playback is already assumed paused."""
        if self._attr_state == MediaPlayerState.PAUSED:
            return

        await self._send_command(PersangSpeakerCode.PLAY_PAUSE.to_command())
        self._attr_state = MediaPlayerState.PAUSED
        self.async_write_ha_state()

    @override
    async def async_media_next_track(self) -> None:
        """Send the next track command."""
        await self._send_command(PersangSpeakerCode.NEXT.to_command())

    @override
    async def async_media_previous_track(self) -> None:
        """Send the previous track command."""
        await self._send_command(PersangSpeakerCode.PREVIOUS.to_command())

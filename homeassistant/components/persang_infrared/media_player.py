"""Media player platform for the Persang Infrared integration."""

from typing import override

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
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_INFRARED_EMITTER_ENTITY_ID
from .entity import PersangIrEntity

PARALLEL_UPDATES = 1

RESTORED_STATES = (
    MediaPlayerState.ON,
    MediaPlayerState.OFF,
    MediaPlayerState.PLAYING,
    MediaPlayerState.PAUSED,
)


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

    @override
    async def async_added_to_hass(self) -> None:
        """Restore the last assumed state."""
        await super().async_added_to_hass()

        if (last_state := await self.async_get_last_state()) is not None and (
            last_state.state in RESTORED_STATES
        ):
            self._attr_state = MediaPlayerState(last_state.state)

    @override
    async def async_turn_on(self) -> None:
        """Send the power command."""
        await self._send_command(PersangSpeakerCode.POWER.to_command())
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    @override
    async def async_turn_off(self) -> None:
        """Send the power command."""
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
        """Send the mute command."""
        await self._send_command(PersangSpeakerCode.MUTE.to_command())
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    @override
    async def async_media_play(self) -> None:
        """Send the play/pause command."""
        await self._send_command(PersangSpeakerCode.PLAY_PAUSE.to_command())
        self._attr_state = MediaPlayerState.PLAYING
        self.async_write_ha_state()

    @override
    async def async_media_pause(self) -> None:
        """Send the play/pause command."""
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

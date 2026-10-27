"""Media player platform for the Croma Infrared integration."""

from typing import override

from infrared_protocols.codes.croma.tv import CromaTVCode

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_INFRARED_EMITTER_ENTITY_ID, DOMAIN
from .entity import CromaIrEntity

PARALLEL_UPDATES = 1

RESTORED_STATES = (
    MediaPlayerState.ON,
    MediaPlayerState.OFF,
    MediaPlayerState.PLAYING,
    MediaPlayerState.PAUSED,
)

SOURCE_TO_CODE: dict[str, CromaTVCode] = {
    "youtube": CromaTVCode.YOUTUBE,
    "netflix": CromaTVCode.NETFLIX,
    "prime_video": CromaTVCode.PRIME_VIDEO,
    "live_tv": CromaTVCode.LIVE_TV,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Croma IR media player from a config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    async_add_entities([CromaIrMediaPlayer(entry, infrared_entity_id)])


class CromaIrMediaPlayer(CromaIrEntity, MediaPlayerEntity, RestoreEntity):
    """Croma IR TV media player entity."""

    _attr_name = None
    _attr_assumed_state = True
    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )
    _attr_source_list = list(SOURCE_TO_CODE)
    _attr_translation_key = "tv"

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
        await self._send_command(CromaTVCode.POWER.to_command())
        self._attr_state = MediaPlayerState.ON
        self.async_write_ha_state()

    @override
    async def async_turn_off(self) -> None:
        """Send the power command."""
        await self._send_command(CromaTVCode.POWER.to_command())
        self._attr_state = MediaPlayerState.OFF
        self.async_write_ha_state()

    @override
    async def async_volume_up(self) -> None:
        """Send the volume up command."""
        await self._send_command(CromaTVCode.VOLUME_UP.to_command())

    @override
    async def async_volume_down(self) -> None:
        """Send the volume down command."""
        await self._send_command(CromaTVCode.VOLUME_DOWN.to_command())

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Send the mute command."""
        await self._send_command(CromaTVCode.MUTE.to_command())
        self._attr_is_volume_muted = mute
        self.async_write_ha_state()

    async def _send_playback_command(
        self, code: CromaTVCode, state: MediaPlayerState
    ) -> None:
        """Send a playback command, keeping an assumed off state."""
        await self._send_command(code.to_command())
        if self.state == MediaPlayerState.OFF:
            return
        self._attr_state = state
        self.async_write_ha_state()

    @override
    async def async_media_play(self) -> None:
        """Send the play command."""
        await self._send_playback_command(CromaTVCode.PLAY, MediaPlayerState.PLAYING)

    @override
    async def async_media_pause(self) -> None:
        """Send the pause command."""
        await self._send_playback_command(CromaTVCode.PAUSE, MediaPlayerState.PAUSED)

    @override
    async def async_media_stop(self) -> None:
        """Send the stop command."""
        await self._send_playback_command(CromaTVCode.STOP, MediaPlayerState.ON)

    @override
    async def async_select_source(self, source: str) -> None:
        """Open the app for the selected source."""
        if (code := SOURCE_TO_CODE.get(source)) is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_source",
                translation_placeholders={
                    "invalid_source": source,
                    "valid_sources": ", ".join(SOURCE_TO_CODE),
                },
            )
        await self._send_command(code.to_command())
        self._attr_source = source
        self.async_write_ha_state()

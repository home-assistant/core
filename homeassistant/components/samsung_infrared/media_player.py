"""Media player platform for Samsung IR integration."""

from infrared_protocols.codes.samsung.tv import SamsungTVCode

from homeassistant.components.infrared import InfraredEmitterConsumerEntity
from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_EMITTER_ENTITY_ID, SamsungDeviceType
from .entity import SamsungIrEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Samsung IR media player from config entry."""
    infrared_emitter_entity_id = entry.data[CONF_INFRARED_EMITTER_ENTITY_ID]
    device_type = entry.data[CONF_DEVICE_TYPE]
    if device_type == SamsungDeviceType.TV:
        async_add_entities([SamsungIrTvMediaPlayer(entry, infrared_emitter_entity_id)])


class SamsungIrTvMediaPlayer(
    SamsungIrEntity, InfraredEmitterConsumerEntity, MediaPlayerEntity
):
    """Samsung IR media player entity."""

    _attr_name = None
    _attr_assumed_state = True
    _attr_device_class = MediaPlayerDeviceClass.TV
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
    )

    def __init__(self, entry: ConfigEntry, infrared_emitter_entity_id: str) -> None:
        """Initialize Samsung IR media player."""
        super().__init__(entry, unique_id_suffix="media_player")
        self._infrared_emitter_entity_id = infrared_emitter_entity_id
        self._attr_state = MediaPlayerState.ON

    async def async_turn_on(self) -> None:
        """Turn on the TV."""
        await self._send_command(SamsungTVCode.POWER_ON.to_command())

    async def async_turn_off(self) -> None:
        """Turn off the TV."""
        await self._send_command(SamsungTVCode.POWER_OFF.to_command())

    async def async_volume_up(self) -> None:
        """Send volume up command."""
        await self._send_command(SamsungTVCode.VOLUME_UP.to_command())

    async def async_volume_down(self) -> None:
        """Send volume down command."""
        await self._send_command(SamsungTVCode.VOLUME_DOWN.to_command())

    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self._send_command(SamsungTVCode.MUTE.to_command())

    async def async_media_next_track(self) -> None:
        """Send channel up command."""
        await self._send_command(SamsungTVCode.CHANNEL_UP.to_command())

    async def async_media_previous_track(self) -> None:
        """Send channel down command."""
        await self._send_command(SamsungTVCode.CHANNEL_DOWN.to_command())

    async def async_media_play(self) -> None:
        """Send play command."""
        await self._send_command(SamsungTVCode.PLAY.to_command())

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._send_command(SamsungTVCode.PAUSE.to_command())

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._send_command(SamsungTVCode.STOP.to_command())

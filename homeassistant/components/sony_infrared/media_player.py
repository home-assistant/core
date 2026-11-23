"""Media player platform for the Sony Infrared integration."""

from typing import override

from infrared_protocols.codes.sony.tv import SonyTVCode

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

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_ENTITY_ID, SonyDeviceType
from .entity import SonyIrEntity

PARALLEL_UPDATES = 1

# A key press on a Sony remote sends at least three identical frames, and some
# devices ignore a single frame.
SIRC_REPEAT_COUNT = 2


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Sony Infrared media player from a config entry."""
    if entry.data[CONF_DEVICE_TYPE] == SonyDeviceType.TV:
        async_add_entities(
            [SonyIrTvMediaPlayer(entry, entry.data[CONF_INFRARED_ENTITY_ID])]
        )


class SonyIrTvMediaPlayer(
    SonyIrEntity, InfraredEmitterConsumerEntity, MediaPlayerEntity
):
    """Sony TV controlled over infrared."""

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
    )

    def __init__(self, entry: ConfigEntry, infrared_entity_id: str) -> None:
        """Initialize the media player."""
        super().__init__(entry, unique_id_suffix="media_player", device_name="Sony TV")
        self._infrared_emitter_entity_id = infrared_entity_id
        self._attr_state = MediaPlayerState.ON

    async def _send_code(self, code: SonyTVCode) -> None:
        """Send a key press of a Sony TV code."""
        command = code.to_command()
        command.repeat_count = SIRC_REPEAT_COUNT
        await self._send_command(command)

    @override
    async def async_turn_on(self) -> None:
        """Turn on the TV with the power toggle."""
        await self._send_code(SonyTVCode.POWER)

    @override
    async def async_turn_off(self) -> None:
        """Turn off the TV with the power toggle."""
        await self._send_code(SonyTVCode.POWER)

    @override
    async def async_volume_up(self) -> None:
        """Send volume up."""
        await self._send_code(SonyTVCode.VOLUME_UP)

    @override
    async def async_volume_down(self) -> None:
        """Send volume down."""
        await self._send_code(SonyTVCode.VOLUME_DOWN)

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Toggle mute, as the TV has no discrete mute codes."""
        await self._send_code(SonyTVCode.MUTE)

    @override
    async def async_media_next_track(self) -> None:
        """Send channel up."""
        await self._send_code(SonyTVCode.CHANNEL_UP)

    @override
    async def async_media_previous_track(self) -> None:
        """Send channel down."""
        await self._send_code(SonyTVCode.CHANNEL_DOWN)

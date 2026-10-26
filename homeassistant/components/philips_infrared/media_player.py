"""Media player platform for Philips IR integration."""

from typing import override

from infrared_protocols.codes.philips.tv import PhilipsTVCode

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PhilipsIrConfigEntry
from .const import CONF_INFRARED_ENTITY_ID
from .entity import PhilipsIrEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PhilipsIrConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Philips IR media player from config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    async_add_entities([PhilipsIrTvMediaPlayer(entry, infrared_entity_id)])


class PhilipsIrTvMediaPlayer(PhilipsIrEntity, MediaPlayerEntity):
    """Philips IR media player entity."""

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

    def __init__(self, entry: PhilipsIrConfigEntry, infrared_entity_id: str) -> None:
        """Initialize Philips IR media player."""
        super().__init__(entry, infrared_entity_id)
        self._attr_state = MediaPlayerState.ON

    # Philips TVs only have a power toggle code, no discrete on and off codes.
    @override
    async def async_turn_on(self) -> None:
        """Send the power command."""
        await self._send_philips_command(PhilipsTVCode.POWER)

    @override
    async def async_turn_off(self) -> None:
        """Send the power command."""
        await self._send_philips_command(PhilipsTVCode.POWER)

    @override
    async def async_volume_up(self) -> None:
        """Send volume up command."""
        await self._send_philips_command(PhilipsTVCode.VOLUME_UP)

    @override
    async def async_volume_down(self) -> None:
        """Send volume down command."""
        await self._send_philips_command(PhilipsTVCode.VOLUME_DOWN)

    @override
    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self._send_philips_command(PhilipsTVCode.MUTE)

    @override
    async def async_media_next_track(self) -> None:
        """Send channel up command."""
        await self._send_philips_command(PhilipsTVCode.CHANNEL_UP)

    @override
    async def async_media_previous_track(self) -> None:
        """Send channel down command."""
        await self._send_philips_command(PhilipsTVCode.CHANNEL_DOWN)

    @override
    async def async_media_play(self) -> None:
        """Send play command."""
        await self._send_philips_command(PhilipsTVCode.PLAY)

    @override
    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._send_philips_command(PhilipsTVCode.PAUSE)

    @override
    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._send_philips_command(PhilipsTVCode.STOP)

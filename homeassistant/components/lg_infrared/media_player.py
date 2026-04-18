"""Media player platform for LG IR integration."""

from __future__ import annotations

from infrared_protocols.codes.lg.tv import LGTVCode

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_DEVICE_TYPE, CONF_INFRARED_ENTITY_ID, LGDeviceType
from .entity import LgIrEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LG IR media player from config entry."""
    infrared_entity_id = entry.data[CONF_INFRARED_ENTITY_ID]
    device_type = entry.data[CONF_DEVICE_TYPE]
    if device_type == LGDeviceType.TV:
        async_add_entities([LgIrTvMediaPlayer(entry, infrared_entity_id)])


class LgIrTvMediaPlayer(LgIrEntity, MediaPlayerEntity):
    """LG IR media player entity."""

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

    def __init__(self, entry: ConfigEntry, infrared_entity_id: str) -> None:
        """Initialize LG IR media player."""
        super().__init__(entry, infrared_entity_id, unique_id_suffix="media_player")
        self._attr_state = MediaPlayerState.ON

    async def async_turn_on(self) -> None:
        """Turn on the TV."""
        await self._send_command(LGTVCode.POWER)

    async def async_turn_off(self) -> None:
        """Turn off the TV."""
        await self._send_command(LGTVCode.POWER)

    async def async_volume_up(self) -> None:
        """Send volume up command."""
        await self._send_command(LGTVCode.VOLUME_UP)

    async def async_volume_down(self) -> None:
        """Send volume down command."""
        await self._send_command(LGTVCode.VOLUME_DOWN)

    async def async_mute_volume(self, mute: bool) -> None:
        """Send mute command."""
        await self._send_command(LGTVCode.MUTE)

    async def async_media_next_track(self) -> None:
        """Send channel up command."""
        await self._send_command(LGTVCode.CHANNEL_UP)

    async def async_media_previous_track(self) -> None:
        """Send channel down command."""
        await self._send_command(LGTVCode.CHANNEL_DOWN)

    async def async_media_play(self) -> None:
        """Send play command."""
        await self._send_command(LGTVCode.PLAY)

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self._send_command(LGTVCode.PAUSE)

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self._send_command(LGTVCode.STOP)

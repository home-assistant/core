"""Support for Axis network speakers."""

import logging
from typing import Any

import axis.ffmpeg

from homeassistant.components import ffmpeg, media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AxisConfigEntry
from .const import DOMAIN as AXIS_DOMAIN
from .entity import AxisEntity
from .hub import AxisHub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: AxisConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add media player for an Axis Network Speaker."""
    hub = config_entry.runtime_data
    vapix = hub.api.vapix

    # only add a media player if both audio APIs are supported
    if vapix.audio.supported and vapix.audio_device_control.supported:
        async_add_entities([AxisSpeaker(hub)])


class AxisSpeaker(AxisEntity, MediaPlayerEntity):
    """Axis Network Speaker."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_media_content_type = MediaType.MUSIC
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )

    def __init__(self, hub: AxisHub) -> None:
        """Initialize the entity."""
        super().__init__(hub)
        self.hub = hub
        self._attr_device_info = DeviceInfo(
            identifiers={(AXIS_DOMAIN, hub.unique_id)},
            serial_number=hub.unique_id,
        )
        self._attr_unique_id = f"{hub.unique_id}_mediaplayer"
        self._attr_state = MediaPlayerState.IDLE

    async def async_update(self) -> None:
        """Sync the current gain/mute settings."""
        gain, mute = await self.hub.api.vapix.audio_device_control.get_gain_mute()
        self._attr_volume_level = self._gain_to_volume(gain)
        self._attr_is_volume_muted = mute

    def _gain_to_volume(self, gain: int) -> float:
        """Convert from Axis gain to HA volume."""
        min_gain = -95
        return (gain - min_gain) / (-min_gain)

    def _volume_to_gain(self, volume: float) -> int:
        """Convert from HA volume to Axis gain."""
        min_gain = -95
        return int(min_gain + (-min_gain * volume))

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        gain = self._volume_to_gain(volume)
        await self.hub.api.vapix.audio_device_control.set_gain(gain)
        self._attr_volume_level = volume

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        if mute:
            await self.hub.api.vapix.audio_device_control.mute()
        else:
            await self.hub.api.vapix.audio_device_control.unmute()
        self._attr_is_volume_muted = mute

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )

    async def async_play_media(
        self, media_type: MediaType | str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        if media_source.is_media_source_id(media_id):
            media_type = MediaType.MUSIC
            play_item = await media_source.async_resolve_media(
                self.hass, media_id, self.entity_id
            )
            media_id = async_process_play_media_url(self.hass, play_item.url)

        if media_type != MediaType.MUSIC:
            raise HomeAssistantError("Only music media type is supported")

        _LOGGER.debug("Playing media %s for axis speaker", media_id)

        ffmpeg_manager = ffmpeg.get_ffmpeg_manager(self.hass)
        data = await axis.ffmpeg.to_axis_mulaw(media_id, ffmpeg_manager.binary)
        if not data:
            raise HomeAssistantError(f"Failed to convert media: {media_id}")

        await self.hub.api.vapix.audio.transmit(data)

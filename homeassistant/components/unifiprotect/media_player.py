"""Support for Ubiquiti's UniFi Protect NVR."""

from __future__ import annotations

import logging
from typing import Any

from uiprotect.data import Camera, ProtectAdoptableDeviceModel, StateType
from uiprotect.exceptions import StreamError

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    async_process_play_media_url,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .data import ProtectDeviceType, UFPConfigEntry
from .entity import ProtectDeviceEntity

_LOGGER = logging.getLogger(__name__)

_SPEAKER_DESCRIPTION = MediaPlayerEntityDescription(
    key="speaker", name="Speaker", device_class=MediaPlayerDeviceClass.SPEAKER
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UFPConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Discover cameras with speakers on a UniFi Protect NVR."""
    data = entry.runtime_data

    @callback
    def _add_new_device(device: ProtectAdoptableDeviceModel) -> None:
        if isinstance(device, Camera) and (
            device.has_speaker or device.has_removable_speaker
        ):
            async_add_entities([ProtectMediaPlayer(data, device)])

    data.async_subscribe_adopt(_add_new_device)
    async_add_entities(
        ProtectMediaPlayer(data, device, _SPEAKER_DESCRIPTION)
        for device in data.get_cameras()
        if device.has_speaker or device.has_removable_speaker
    )


class ProtectMediaPlayer(ProtectDeviceEntity, MediaPlayerEntity):
    """A Ubiquiti UniFi Protect Speaker."""

    device: Camera
    entity_description: MediaPlayerEntityDescription
    _attr_supported_features = (
        MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )
    _attr_media_content_type = MediaType.MUSIC
    _state_attrs = ("_attr_available", "_attr_state", "_attr_volume_level")

    @callback
    def _async_update_device_from_protect(self, device: ProtectDeviceType) -> None:
        super()._async_update_device_from_protect(device)
        updated_device = self.device
        self._attr_volume_level = float(updated_device.speaker_settings.volume / 100)

        if (
            updated_device.talkback_stream is not None
            and updated_device.talkback_stream.is_running
        ):
            self._attr_state = MediaPlayerState.PLAYING
        else:
            self._attr_state = MediaPlayerState.IDLE

        is_connected = self.data.last_update_success and (
            updated_device.state is StateType.CONNECTED
            or (not updated_device.is_adopted_by_us and updated_device.can_adopt)
        )
        self._attr_available = is_connected and updated_device.feature_flags.has_speaker

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""

        volume_int = int(volume * 100)
        await self.device.set_speaker_volume(volume_int)

    async def async_media_stop(self) -> None:
        """Send stop command."""

        if (
            self.device.talkback_stream is not None
            and self.device.talkback_stream.is_running
        ):
            _LOGGER.debug("Stopping playback for %s Speaker", self.device.display_name)
            await self.device.stop_audio()
            self._async_updated_event(self.device)

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

        _LOGGER.debug(
            "Playing Media %s for %s Speaker", media_id, self.device.display_name
        )
        await self.async_media_stop()
        try:
            await self.device.play_audio(media_id, blocking=False)
        except StreamError as err:
            raise HomeAssistantError(err) from err

        # update state after starting player
        self._async_updated_event(self.device)
        # wait until player finishes to update state again
        await self.device.wait_until_audio_completes()

        self._async_updated_event(self.device)

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

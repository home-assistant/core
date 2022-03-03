"""Support for Ubiquiti's UniFi Protect NVR."""
from __future__ import annotations

import logging
from typing import Any

from pyunifiprotect.data import Camera
from pyunifiprotect.exceptions import StreamError

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityDescription,
)
from homeassistant.components.media_player.browse_media import (
    async_process_play_media_url,
)
from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MUSIC,
    SUPPORT_BROWSE_MEDIA,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_STOP,
    SUPPORT_VOLUME_SET,
    SUPPORT_VOLUME_STEP,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE, STATE_PLAYING
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .data import ProtectData
from .entity import ProtectDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Discover cameras with speakers on a UniFi Protect NVR."""
    data: ProtectData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            ProtectMediaPlayer(
                data,
                camera,
            )
            for camera in data.api.bootstrap.cameras.values()
            if camera.feature_flags.has_speaker
        ]
    )


class ProtectMediaPlayer(ProtectDeviceEntity, MediaPlayerEntity):
    """A Ubiquiti UniFi Protect Speaker."""

    device: Camera
    entity_description: MediaPlayerEntityDescription

    def __init__(
        self,
        data: ProtectData,
        camera: Camera,
    ) -> None:
        """Initialize an UniFi speaker."""
        super().__init__(
            data,
            camera,
            MediaPlayerEntityDescription(
                key="speaker", device_class=MediaPlayerDeviceClass.SPEAKER
            ),
        )

        self._attr_name = f"{self.device.name} Speaker"
        self._attr_supported_features = (
            SUPPORT_PLAY_MEDIA
            | SUPPORT_VOLUME_SET
            | SUPPORT_VOLUME_STEP
            | SUPPORT_STOP
            | SUPPORT_BROWSE_MEDIA
        )
        self._attr_media_content_type = MEDIA_TYPE_MUSIC

    @callback
    def _async_update_device_from_protect(self) -> None:
        super()._async_update_device_from_protect()
        self._attr_volume_level = float(self.device.speaker_settings.volume / 100)

        if (
            self.device.talkback_stream is not None
            and self.device.talkback_stream.is_running
        ):
            self._attr_state = STATE_PLAYING
        else:
            self._attr_state = STATE_IDLE

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
            _LOGGER.debug("Stopping playback for %s Speaker", self.device.name)
            await self.device.stop_audio()
            self._async_updated_event()

    async def async_play_media(
        self, media_type: str, media_id: str, **kwargs: Any
    ) -> None:
        """Play a piece of media."""
        if media_source.is_media_source_id(media_id):
            media_type = MEDIA_TYPE_MUSIC
            play_item = await media_source.async_resolve_media(self.hass, media_id)
            media_id = play_item.url

        if media_type != MEDIA_TYPE_MUSIC:
            raise ValueError("Only music media type is supported")

        media_id = async_process_play_media_url(self.hass, media_id)

        _LOGGER.debug("Playing Media %s for %s Speaker", media_id, self.device.name)
        await self.async_media_stop()
        try:
            await self.device.play_audio(media_id, blocking=False)
        except StreamError as err:
            raise HomeAssistantError from err
        else:
            # update state after starting player
            self._async_updated_event()
            # wait until player finishes to update state again
            await self.device.wait_until_audio_completes()

        self._async_updated_event()

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )

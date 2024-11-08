"""Support for Axis network speakers."""

import asyncio
import logging
from typing import Any

import httpx

from homeassistant.components import ffmpeg, media_source
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
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.httpx_client import get_async_client

from . import AxisConfigEntry
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
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.BROWSE_MEDIA
    )
    entity_description: MediaPlayerEntityDescription

    def __init__(self, hub: AxisHub) -> None:
        """Initialize the entity."""
        super().__init__(hub)
        self._attr_unique_id = f"{hub.unique_id}_mediaplayer"
        self._attr_state = MediaPlayerState.IDLE

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

        _LOGGER.debug("playing media %s for axis speaker", media_id)

        ffmpeg_manager = ffmpeg.get_ffmpeg_manager(self.hass)
        output = await ffmpeg_cmd(ffmpeg_manager.binary, media_id)

        uri = "/axis-cgi/audio/transmit.cgi"
        conf = self.hub.config
        url = f"{conf.protocol}://{conf.host}:{conf.port}{uri}"
        auth = httpx.DigestAuth(self.hub.config.username, self.hub.config.password)
        headers = {"Content-Type": "audio/axis-mulaw-128"}

        client = get_async_client(self.hass, verify_ssl=False)
        await client.post(url, headers=headers, content=output, auth=auth)

    async def async_media_stop(self) -> None:
        """Send stop command."""

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""


async def ffmpeg_cmd(ffmpeg_path: str, media_id: str) -> bytes:
    """Convert media to Axis-compatible format."""
    args = [
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        media_id,
        "-vn",
        "-probesize",
        "32",
        "-analyzeduration",
        "32",
        "-c:a",
        "pcm_mulaw",
        "-ab",
        "128k",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-f",
        "wav",
        "-",
    ]

    _LOGGER.debug("ffmpeg_cmd: %s %s", ffmpeg_path, " ".join(args))

    process = await asyncio.create_subprocess_exec(
        ffmpeg_path,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return stdout

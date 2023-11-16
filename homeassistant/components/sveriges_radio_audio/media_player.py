"""Media player class for Sveriges Radio."""

from typing import Any

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseMedia,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    MediaType,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .sveriges_radio import sveriges_radio


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Media Player."""
    async_add_entities([MyMediaPlayer()])


class MyMediaPlayer(MediaPlayerEntity):
    """Class for Media Player."""

    @property
    def media_content_type(self):
        """Content type of current playing media."""
        return MediaType.URL

    async def async_browse_media(
        self,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> BrowseMedia:
        """Implement the websocket media browsing helper."""
        # If your media player has no own media sources to browse, route all browse commands
        # to the media source integration.
        return await media_source.async_browse_media(
            self.hass,
            media_content_id,
            # This allows filtering content. In this case it will only show audio sources.
            content_filter=lambda item: item.media_content_type.startswith("audio/"),
        )

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        enqueue: MediaPlayerEnqueue | None = None,
        announce: bool | None = None,
        **kwargs: Any,
    ) -> None:
        """Play a piece of media."""
        sr_radio = sveriges_radio(None, "user1", None)
        resp = sr_radio.call_sr_api()
        channels = sr_radio.get_sr_channels(response_sr=resp)
        channel_P1 = sr_radio.get_sr_channel(channels=channels, station=132)
        url = sr_radio.get_sr_audio(channel=channel_P1)
        return url

    def select_sound_mode(self, sound_mode):
        """Switch the sound mode of the entity."""

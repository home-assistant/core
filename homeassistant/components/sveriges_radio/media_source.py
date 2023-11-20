"""Expose Sveriges Radio as a media source."""
from __future__ import annotations

from homeassistant.components.media_player import BrowseError, MediaClass, MediaType
from homeassistant.components.media_source.error import Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .sveriges_radio import Channel, SverigesRadio


async def async_get_media_source(hass: HomeAssistant) -> RadioMediaSource:
    """Set up Sveriges Radio media source."""
    # Sveriges Radio supports only a single config entry
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    return RadioMediaSource(hass, entry)


class RadioMediaSource(MediaSource):
    """Provide Radio stations as media sources."""

    name = "Sveriges Radio"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize RadioMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass
        self.entry = entry

    @property
    def radio(self) -> SverigesRadio | None:
        """Return the Sveriges Radio."""
        return self.hass.data.get(DOMAIN)

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve selected Radio station to a streaming URL."""
        radio = self.radio

        if radio is None:
            raise Unresolvable("Sveriges Radio not initialized")

        station = await radio.channel(station_id=item.identifier)

        if not station:
            raise Unresolvable("Radio station is no longer available")

        if not (mime_type := "audio/mpeg"):
            raise Unresolvable("Could not determine stream type of radio station")

        return PlayMedia(station.url, mime_type)

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        radio = self.radio

        if radio is None:
            raise BrowseError("Sveriges Radio not initialized")

        # Check if the item is the root of the media source
        if item.identifier is None:
            # Fetch all channels
            channels = await radio.channels()
            channel_media_sources = await self._async_build_stations(channels)

            # Create a root BrowseMediaSource object and include the channels as children
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=None,
                media_class=MediaClass.DIRECTORY,
                media_content_type=MediaType.APP,
                title="Sveriges Radio",
                can_play=False,
                can_expand=True,
                children=channel_media_sources,
            )

        # Fallback for unhandled cases
        raise BrowseError("Item not found")

    @callback
    async def _async_build_stations(
        self, channels: list[Channel]
    ) -> list[BrowseMediaSource]:
        """Build list of media sources for channels."""
        media_sources = []
        for channel in channels:
            # Create a BrowseMediaSource object for each channel
            channel_media = BrowseMediaSource(
                domain=DOMAIN,
                identifier=str(channel.station_id),
                media_class=MediaClass.MUSIC,
                media_content_type=MediaType.MUSIC,
                title=channel.name,
                can_play=True,
                can_expand=False,
                thumbnail=channel.image,
            )
            media_sources.append(channel_media)

        return media_sources

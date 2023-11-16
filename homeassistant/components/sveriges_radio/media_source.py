"""Expose Sveriges Radio as a media source."""
from __future__ import annotations

import mimetypes

from sverigesradio import Channel, SverigesRadio

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

CODEC_TO_MIMETYPE = {
    "MP3": "audio/mpeg",
    "AAC": "audio/aac",
    "AAC+": "audio/aac",
    "OGG": "application/ogg",
}


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

        station = await radio.channel(164)
        if not station:
            raise Unresolvable("Radio station is no longer available")

        if not (mime_type := self._async_get_station_mime_type(station)):
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

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.CHANNEL,
            media_content_type=MediaType.MUSIC,
            title=self.entry.title,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
        )

    @callback
    @staticmethod
    def _async_get_station_mime_type(station: Channel) -> str | None:
        """Determine mime type of a radio station."""
        mime_type = CODEC_TO_MIMETYPE.get("MP3")
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(station.url)
        return mime_type

    @callback
    def _async_build_stations(
        self, radios: SverigesRadio, stations: list[Channel]
    ) -> list[BrowseMediaSource]:
        """Build list of media sources from radio stations."""
        items: list[BrowseMediaSource] = []

        for station in stations:
            mime_type = self._async_get_station_mime_type(station)

            items.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=station.id,
                    media_class=MediaClass.MUSIC,
                    media_content_type=mime_type,
                    title=station.name,
                    can_play=True,
                    can_expand=False,
                    thumbnail=station.image,
                )
            )

        return items

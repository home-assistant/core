"""Expose Radio Browser as a media source."""
from __future__ import annotations

import mimetypes

from radios import FilterBy, Order, RadioBrowser

from homeassistant.components.media_player.const import (
    MEDIA_CLASS_CHANNEL,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_MUSIC,
    MEDIA_TYPE_MUSIC,
)
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

CODEC_TO_MIMETYPE = {
    "MP3": "audio/mpeg",
    "AAC": "audio/aac",
    "AAC+": "audio/aac",
    "OGG": "application/ogg",
}


async def async_get_media_source(hass: HomeAssistant) -> RadioMediaSource:
    """Set up Radio Browser media source."""
    # Radio browser support only a single config entry
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    radios = hass.data[DOMAIN]

    return RadioMediaSource(hass, radios, entry)


class RadioMediaSource(MediaSource):
    """Provide Radio stations as media sources."""

    def __init__(
        self, hass: HomeAssistant, radios: RadioBrowser, entry: ConfigEntry
    ) -> None:
        """Initialize CameraMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass
        self.entry = entry
        self.radios = radios

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve selected Radio station to a streaming URL."""
        station = await self.radios.station(uuid=item.identifier)
        if not station:
            raise BrowseError("Radio station is no longer available")

        # Determine mime type
        mime_type = CODEC_TO_MIMETYPE.get(station.codec)
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(station.url)
        if not mime_type:
            raise BrowseError("Could not determine stream type of radio station")

        # Register "click" with Radio Browser
        await self.radios.station_click(uuid=station.uuid)

        return PlayMedia(station.url, mime_type)

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        root = BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MEDIA_CLASS_CHANNEL,
            media_content_type=MEDIA_TYPE_MUSIC,
            title=self.entry.title,
            can_play=False,
            can_expand=True,
            children_media_class=MEDIA_CLASS_DIRECTORY,
        )
        root.children = []

        # Browsing stations
        if item.identifier:
            stations = []
            if item.identifier == "popular":
                stations = await self.radios.stations(
                    hide_broken=True, limit=256, order=Order.CLICK_COUNT, reverse=True
                )
            else:
                stations = await self.radios.stations(
                    filter_by=FilterBy.COUNTRY_CODE_EXACT,
                    filter_term=item.identifier,
                    hide_broken=True,
                    order=Order.CLICK_COUNT,
                    reverse=True,
                )

            if stations:
                for station in stations:
                    play_station = BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=station.uuid,
                        media_class=MEDIA_CLASS_MUSIC,
                        media_content_type=CODEC_TO_MIMETYPE.get(station.codec, ""),
                        title=station.name,
                        can_play=True,
                        can_expand=False,
                        thumbnail=station.favicon,
                    )
                    root.children.append(play_station)
            return root

        # Add a popular directory
        folder = BrowseMediaSource(
            domain=DOMAIN,
            identifier="popular",
            media_class=MEDIA_CLASS_DIRECTORY,
            media_content_type=MEDIA_TYPE_MUSIC,
            title="Popular",
            can_play=False,
            can_expand=True,
        )
        root.children.append(folder)

        # Add countries
        countries = await self.radios.countries(order=Order.NAME)
        for country in countries:
            country_source = BrowseMediaSource(
                domain=DOMAIN,
                identifier=country.code,
                media_class=MEDIA_CLASS_DIRECTORY,
                media_content_type=MEDIA_TYPE_MUSIC,
                title=country.name,
                can_play=False,
                can_expand=True,
                thumbnail=country.favicon,
            )
            root.children.append(country_source)

        return root

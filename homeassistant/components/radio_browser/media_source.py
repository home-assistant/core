"""Expose Radio Browser as a media source."""
from __future__ import annotations

import mimetypes

from radios import FilterBy, Order, RadioBrowser, Station

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
    """Set up Radio Browser media source."""
    # Radio browser supports only a single config entry
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    return RadioMediaSource(hass, entry)


class RadioMediaSource(MediaSource):
    """Provide Radio stations as media sources."""

    name = "Radio Browser"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize RadioMediaSource."""
        super().__init__(DOMAIN)
        self.hass = hass
        self.entry = entry

    @property
    def radios(self) -> RadioBrowser | None:
        """Return the radio browser."""
        return self.hass.data.get(DOMAIN)

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve selected Radio station to a streaming URL."""
        radios = self.radios

        if radios is None:
            raise Unresolvable("Radio Browser not initialized")

        station = await radios.station(uuid=item.identifier)
        if not station:
            raise Unresolvable("Radio station is no longer available")

        if not (mime_type := self._async_get_station_mime_type(station)):
            raise Unresolvable("Could not determine stream type of radio station")

        # Register "click" with Radio Browser
        await radios.station_click(uuid=station.uuid)

        return PlayMedia(station.url, mime_type)

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Return media."""
        radios = self.radios

        if radios is None:
            raise BrowseError("Radio Browser not initialized")

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.CHANNEL,
            media_content_type=MediaType.MUSIC,
            title=self.entry.title,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=[
                *await self._async_build_popular(radios, item),
                *await self._async_build_by_tag(radios, item),
                *await self._async_build_by_language(radios, item),
                *await self._async_build_by_country(radios, item),
            ],
        )

    @callback
    @staticmethod
    def _async_get_station_mime_type(station: Station) -> str | None:
        """Determine mime type of a radio station."""
        mime_type = CODEC_TO_MIMETYPE.get(station.codec)
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(station.url)
        return mime_type

    @callback
    def _async_build_stations(
        self, radios: RadioBrowser, stations: list[Station]
    ) -> list[BrowseMediaSource]:
        """Build list of media sources from radio stations."""
        items: list[BrowseMediaSource] = []

        for station in stations:
            if station.codec == "UNKNOWN" or not (
                mime_type := self._async_get_station_mime_type(station)
            ):
                continue

            items.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=station.uuid,
                    media_class=MediaClass.MUSIC,
                    media_content_type=mime_type,
                    title=station.name,
                    can_play=True,
                    can_expand=False,
                    thumbnail=station.favicon,
                )
            )

        return items

    async def _async_build_by_country(
        self, radios: RadioBrowser, item: MediaSourceItem
    ) -> list[BrowseMediaSource]:
        """Handle browsing radio stations by country."""
        category, _, country_code = (item.identifier or "").partition("/")
        if country_code:
            stations = await radios.stations(
                filter_by=FilterBy.COUNTRY_CODE_EXACT,
                filter_term=country_code,
                hide_broken=True,
                order=Order.NAME,
                reverse=False,
            )
            return self._async_build_stations(radios, stations)

        # We show country in the root additionally, when there is no item
        if not item.identifier or category == "country":
            countries = await radios.countries(order=Order.NAME)
            return [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"country/{country.code}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title=country.name,
                    can_play=False,
                    can_expand=True,
                    thumbnail=country.favicon,
                )
                for country in countries
            ]

        return []

    async def _async_build_by_language(
        self, radios: RadioBrowser, item: MediaSourceItem
    ) -> list[BrowseMediaSource]:
        """Handle browsing radio stations by language."""
        category, _, language = (item.identifier or "").partition("/")
        if category == "language" and language:
            stations = await radios.stations(
                filter_by=FilterBy.LANGUAGE_EXACT,
                filter_term=language,
                hide_broken=True,
                order=Order.NAME,
                reverse=False,
            )
            return self._async_build_stations(radios, stations)

        if category == "language":
            languages = await radios.languages(order=Order.NAME, hide_broken=True)
            return [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"language/{language.code}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title=language.name,
                    can_play=False,
                    can_expand=True,
                    thumbnail=language.favicon,
                )
                for language in languages
            ]

        if not item.identifier:
            return [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier="language",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title="By Language",
                    can_play=False,
                    can_expand=True,
                )
            ]

        return []

    async def _async_build_popular(
        self, radios: RadioBrowser, item: MediaSourceItem
    ) -> list[BrowseMediaSource]:
        """Handle browsing popular radio stations."""
        if item.identifier == "popular":
            stations = await radios.stations(
                hide_broken=True,
                limit=250,
                order=Order.CLICK_COUNT,
                reverse=True,
            )
            return self._async_build_stations(radios, stations)

        if not item.identifier:
            return [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier="popular",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title="Popular",
                    can_play=False,
                    can_expand=True,
                )
            ]

        return []

    async def _async_build_by_tag(
        self, radios: RadioBrowser, item: MediaSourceItem
    ) -> list[BrowseMediaSource]:
        """Handle browsing radio stations by tags."""
        category, _, tag = (item.identifier or "").partition("/")
        if category == "tag" and tag:
            stations = await radios.stations(
                filter_by=FilterBy.TAG_EXACT,
                filter_term=tag,
                hide_broken=True,
                order=Order.NAME,
                reverse=False,
            )
            return self._async_build_stations(radios, stations)

        if category == "tag":
            tags = await radios.tags(
                hide_broken=True,
                limit=100,
                order=Order.STATION_COUNT,
                reverse=True,
            )

            # Now we have the top tags, reorder them by name
            tags.sort(key=lambda tag: tag.name)

            return [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"tag/{tag.name}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title=tag.name.title(),
                    can_play=False,
                    can_expand=True,
                )
                for tag in tags
            ]

        if not item.identifier:
            return [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier="tag",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title="By Category",
                    can_play=False,
                    can_expand=True,
                )
            ]

        return []

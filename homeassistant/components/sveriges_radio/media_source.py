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

from .const import DOMAIN, ERROR_MESSAGE_NOT_INITIALIZED, FOLDERNAME
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
            raise Unresolvable(ERROR_MESSAGE_NOT_INITIALIZED)

        station = await radio.resolve_station(station_id=item.identifier)

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
            raise BrowseError(ERROR_MESSAGE_NOT_INITIALIZED)

        category, _, program_info = (item.identifier or "").partition("/")

        if category == FOLDERNAME and program_info:
            program = await radio.program(program_info)
            title = program.name
        elif category == FOLDERNAME:
            title = FOLDERNAME
        else:
            title = "Sveriges Radio"

        # Create a root BrowseMediaSource object and include the channels as children
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=None,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.MUSIC,
            title=title,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.DIRECTORY,
            children=[
                *await self._async_build_channels(item),
                *await self._async_build_programs(item),
            ],
        )

    @callback
    async def _async_build_channels(
        self,
        item: MediaSourceItem,
    ) -> list[BrowseMediaSource]:
        """Build list of channels."""
        category, _, _ = (item.identifier or "").partition("/")

        if not category:
            radio = self.radio

            if radio is None:
                raise BrowseError(ERROR_MESSAGE_NOT_INITIALIZED)

            channels = await radio.channels()

            media_sources = []
            for channel in channels:
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

        return []

    @callback
    async def _async_build_programs(
        self,
        item: MediaSourceItem,
    ) -> list[BrowseMediaSource]:
        """Build list of programs."""
        radio = self.radio

        if radio is None:
            raise BrowseError(ERROR_MESSAGE_NOT_INITIALIZED)

        category, _, program_code = (item.identifier or "").partition("/")

        if program_code and category == FOLDERNAME:
            program = await radio.program(program_code)
            return await self._async_build_podcasts(program)

        if category == FOLDERNAME:
            programs = await radio.programs(programs_list=[])

            media_sources: list[BrowseMediaSource] = []

            for program in programs:
                program_media = BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{FOLDERNAME}/{program.station_id}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title=program.name,
                    can_play=False,
                    can_expand=True,
                    thumbnail=program.image,
                )
                media_sources.append(program_media)

            return media_sources

        if not item.identifier:
            return [
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=FOLDERNAME,
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.MUSIC,
                    title=FOLDERNAME,
                    can_play=False,
                    can_expand=True,
                    thumbnail="https://www.pngarts.com/files/7/Podcast-Symbol-Transparent-Background-PNG.png",
                )
            ]

        return []

    @callback
    async def _async_build_podcasts(self, program: Channel) -> list[BrowseMediaSource]:
        """Build list of podcasts for a program."""
        radio = self.radio

        if radio is None:
            raise BrowseError(ERROR_MESSAGE_NOT_INITIALIZED)

        podcasts = await radio.podcasts(program_id=program.station_id, podcasts_list=[])

        media_sources = []
        for podcast in podcasts:
            podcast_media = BrowseMediaSource(
                domain=DOMAIN,
                identifier=podcast.station_id,
                media_class=MediaClass.MUSIC,
                media_content_type=MediaType.MUSIC,
                title=podcast.name,
                can_play=True,
                can_expand=False,
                thumbnail=podcast.image,
            )
            media_sources.append(podcast_media)

        return media_sources

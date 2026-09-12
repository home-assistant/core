"""Expose podcasts as a media source."""

import mimetypes
from typing import override
from urllib.parse import urlsplit

from aiopodcast import Podcast, PodcastEpisode

from homeassistant.components.media_player import BrowseError, MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .const import DOMAIN, MAX_BROWSE_EPISODES
from .coordinator import PodcastConfigEntry
from .helpers import episode_identifier


async def async_get_media_source(hass: HomeAssistant) -> PodcastMediaSource:
    """Set up the Podcast Player media source."""
    return PodcastMediaSource(hass)


def _episode_mime_type(episode: PodcastEpisode) -> str:
    """Return the episode MIME type."""
    if episode.enclosure.mime_type:
        return episode.enclosure.mime_type.partition(";")[0].strip()
    mime_type, _ = mimetypes.guess_type(urlsplit(episode.enclosure.url).path)
    return mime_type or "audio/mpeg"


def _find_episode(podcast: Podcast, identifier: str) -> PodcastEpisode | None:
    """Find an episode by its media source identifier."""
    return next(
        (
            episode
            for episode in podcast.episodes
            if episode_identifier(episode) == identifier
        ),
        None,
    )


class PodcastMediaSource(MediaSource):
    """Provide configured podcasts as a media source."""

    name = "Podcasts"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the podcast media source."""
        super().__init__(DOMAIN)
        self.hass = hass

    def _loaded_entries(self) -> list[PodcastConfigEntry]:
        """Return loaded podcast entries."""
        return self.hass.config_entries.async_loaded_entries(DOMAIN)

    def _entries(self) -> list[PodcastConfigEntry]:
        """Return configured podcast entries."""
        return self.hass.config_entries.async_entries(DOMAIN)

    def _entry(self, entry_id: str) -> PodcastConfigEntry | None:
        """Return a configured podcast entry by entry ID."""
        return next(
            (entry for entry in self._entries() if entry.entry_id == entry_id),
            None,
        )

    @override
    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Browse configured podcasts and episodes."""
        entries = self._loaded_entries()
        if not entries:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key=(
                    "feed_unavailable" if self._entries() else "not_configured"
                ),
            )

        if not item.identifier:
            return BrowseMediaSource(
                domain=DOMAIN,
                identifier=None,
                media_class=MediaClass.PODCAST,
                media_content_type=MediaType.PODCAST,
                title="Podcasts",
                can_play=False,
                can_expand=True,
                children_media_class=MediaClass.PODCAST,
                children=[
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=entry.entry_id,
                        media_class=MediaClass.PODCAST,
                        media_content_type=MediaType.PODCAST,
                        title=entry.title,
                        can_play=False,
                        can_expand=True,
                        children_media_class=MediaClass.EPISODE,
                        thumbnail=entry.runtime_data.data.artwork_url,
                    )
                    for entry in sorted(
                        entries, key=lambda entry: entry.title.casefold()
                    )
                ],
            )

        if "/" in item.identifier or not (entry := self._entry(item.identifier)):
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="path_not_found",
            )
        if entry.state is not ConfigEntryState.LOADED:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="feed_unavailable",
            )

        await entry.runtime_data.async_refresh()
        if not entry.runtime_data.last_update_success:
            raise BrowseError(
                translation_domain=DOMAIN,
                translation_key="feed_unavailable",
            ) from entry.runtime_data.last_exception
        podcast = entry.runtime_data.data

        episodes = podcast.episodes[:MAX_BROWSE_EPISODES]
        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=entry.entry_id,
            media_class=MediaClass.PODCAST,
            media_content_type=MediaType.PODCAST,
            title=podcast.title,
            can_play=False,
            can_expand=True,
            children_media_class=MediaClass.EPISODE,
            thumbnail=podcast.artwork_url,
            not_shown=len(podcast.episodes) - len(episodes),
            children=[
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{entry.entry_id}/{episode_identifier(episode)}",
                    media_class=MediaClass.EPISODE,
                    media_content_type=_episode_mime_type(episode),
                    title=episode.title,
                    can_play=True,
                    can_expand=False,
                    thumbnail=episode.artwork_url or podcast.artwork_url,
                )
                for episode in episodes
            ],
        )

    @override
    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a podcast episode to its enclosure URL."""
        entry_id, separator, episode_id = item.identifier.partition("/")
        if not separator or not episode_id or not (entry := self._entry(entry_id)):
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="episode_unavailable",
            )
        if entry.state is not ConfigEntryState.LOADED:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="feed_unavailable",
            )

        episode = _find_episode(entry.runtime_data.data, episode_id)
        if episode is None:
            await entry.runtime_data.async_refresh()
            if not entry.runtime_data.last_update_success:
                raise Unresolvable(
                    translation_domain=DOMAIN,
                    translation_key="feed_unavailable",
                ) from entry.runtime_data.last_exception
            podcast = entry.runtime_data.data
            episode = _find_episode(podcast, episode_id)

        if episode is None:
            raise Unresolvable(
                translation_domain=DOMAIN,
                translation_key="episode_unavailable",
            )

        return PlayMedia(
            url=episode.enclosure.url,
            mime_type=_episode_mime_type(episode),
        )

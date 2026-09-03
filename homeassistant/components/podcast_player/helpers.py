"""Shared helpers for Podcast Player."""

import hashlib

from aiopodcast import PodcastEpisode


def episode_identifier(episode: PodcastEpisode) -> str:
    """Return a stable identifier for a podcast episode."""
    value = episode.guid or episode.enclosure.url
    return hashlib.sha256(value.encode()).hexdigest()[:32]

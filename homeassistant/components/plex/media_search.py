"""Helper methods to search for Plex media."""
from __future__ import annotations

import logging

from plexapi.base import PlexObject
from plexapi.exceptions import BadRequest, NotFound
from plexapi.library import LibrarySection

from .errors import MediaNotFound

LEGACY_PARAM_MAPPING = {
    "show_name": "show.title",
    "season_number": "season.index",
    "episode_name": "episode.title",
    "episode_number": "episode.index",
    "artist_name": "artist.title",
    "album_name": "album.title",
    "track_name": "track.title",
    "track_number": "track.index",
    "video_name": "movie.title",
}

PREFERRED_LIBTYPE_ORDER = (
    "episode",
    "season",
    "show",
    "track",
    "album",
    "artist",
)


_LOGGER = logging.getLogger(__name__)


def search_media(
    media_type: str,
    library_section: LibrarySection,
    allow_multiple: bool = False,
    **kwargs,
) -> PlexObject | list[PlexObject]:
    """Search for specified Plex media in the provided library section.

    Returns a media item or a list of items if `allow_multiple` is set.

    Raises MediaNotFound if the search was unsuccessful.
    """
    original_query = kwargs.copy()
    search_query = {}
    libtype = kwargs.pop("libtype", None)

    # Preserve legacy service parameters
    for legacy_key, key in LEGACY_PARAM_MAPPING.items():
        if value := kwargs.pop(legacy_key, None):
            _LOGGER.debug(
                "Legacy parameter '%s' used, consider using '%s'", legacy_key, key
            )
            search_query[key] = value

    search_query.update(**kwargs)

    if not libtype:
        # Default to a sane libtype if not explicitly provided
        for preferred_libtype in PREFERRED_LIBTYPE_ORDER:
            if any(key.startswith(preferred_libtype) for key in search_query):
                libtype = preferred_libtype
                break

    search_query.update(libtype=libtype)
    _LOGGER.debug("Processed search query: %s", search_query)

    try:
        results = library_section.search(**search_query)
    except (BadRequest, NotFound) as exc:
        raise MediaNotFound(f"Problem in query {original_query}: {exc}") from exc

    if not results:
        raise MediaNotFound(
            f"No {media_type} results in '{library_section.title}' for {original_query}"
        )

    if len(results) > 1:
        if allow_multiple:
            return results

        if title := search_query.get("title") or search_query.get("movie.title"):
            exact_matches = [x for x in results if x.title.lower() == title.lower()]
            if len(exact_matches) == 1:
                return exact_matches[0]
        raise MediaNotFound(
            f"Multiple matches, make content_id more specific or use `allow_multiple`: {results}"
        )

    return results[0]

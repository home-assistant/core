"""Helper methods to search for Plex media."""
import logging

from plexapi.exceptions import BadRequest, NotFound

from homeassistant.components.media_player.const import (
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_VIDEO,
)

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


_LOGGER = logging.getLogger(__name__)


def search_media(media_type, library_section, **kwargs):
    """Search for specified Plex media in the provided library section.

    Returns a single media item or None.
    """
    search_query = {}
    libtype = kwargs.pop("libtype", None)

    # Preserve legacy service parameters
    for legacy_key, key in LEGACY_PARAM_MAPPING.items():
        if value := kwargs.pop(legacy_key, None):
            _LOGGER.debug(
                "Legacy parameter '%s' used, consider using '%s'", legacy_key, key
            )
            search_query[key] = value
    if media_type in [MEDIA_TYPE_MOVIE, MEDIA_TYPE_VIDEO]:
        if title := kwargs.pop("title", None):
            search_query["movie.title"] = title

    search_query.update(**kwargs)

    if not libtype:
        # Default to a sane libtype if not explicitly provided
        for libtype in [
            "movie",
            "episode",
            "season",
            "show",
            "track",
            "album",
            "artist",
            None,
        ]:
            if not libtype or any(key.startswith(libtype) for key in search_query):
                break

    search_query.update(libtype=libtype)
    _LOGGER.debug("Processed search query: %s", search_query)

    try:
        results = library_section.search(**search_query)
    except (BadRequest, NotFound) as exc:
        _LOGGER.error("Problem in query %s: %s", search_query, exc)
        return None

    if not results:
        return None

    if len(results) > 1:
        if title := search_query.get("title") or search_query.get("movie.title"):
            exact_matches = [x for x in results if x.title.lower() == title.lower()]
            if len(exact_matches) == 1:
                return exact_matches[0]
        _LOGGER.warning("Multiple matches, make content_id more specific: %s", results)
        return None

    return results[0]

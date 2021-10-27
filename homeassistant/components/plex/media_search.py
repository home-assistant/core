"""Helper methods to search for Plex media."""
import logging

from plexapi.exceptions import BadRequest, NotFound

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


def search_media(media_type, library_section, allow_multiple=False, **kwargs):
    """Search for specified Plex media in the provided library section.

    Returns a single media item or None.

    If `allow_multiple` is `True`, return a list of matching items.
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
        _LOGGER.error("Problem in query %s: %s", search_query, exc)
        return None

    if not results:
        return None

    if len(results) > 1:
        if allow_multiple:
            return results

        if title := search_query.get("title") or search_query.get("movie.title"):
            exact_matches = [x for x in results if x.title.lower() == title.lower()]
            if len(exact_matches) == 1:
                return exact_matches[0]
        _LOGGER.warning(
            "Multiple matches, make content_id more specific or use `allow_multiple`: %s",
            results,
        )
        return None

    return results[0]

"""Helper methods to search for Plex media."""

from difflib import SequenceMatcher
import logging
import re
from typing import TYPE_CHECKING, Any
import unicodedata

from plexapi.base import PlexObject
from plexapi.exceptions import BadRequest, NotFound
from plexapi.library import LibrarySection

from .errors import MediaNotFound

if TYPE_CHECKING:
    from .server import PlexServer

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
            "Multiple matches, make content_id more specific or use `allow_multiple`:"
            f" {results}"
        )

    return results[0]


FUZZY_MIN_SCORE = 0.6
FUZZY_LIMIT = 10
SECTION_TYPE_FOR_MEDIATYPE = {
    "movie": "movie",
    "show": "show",
    "season": "show",
    "episode": "show",
    "artist": "artist",
    "album": "artist",
    "track": "artist",
}
SEARCHABLE_SECTION_TYPES = {"movie", "show", "artist"}
IGNORED_LEADING_WORDS = {"the", "a", "an"}


def normalize_title(text: str) -> str:
    """Normalize a title for comparison, ignoring case, accents and punctuation."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    words = re.sub(r"[^a-z0-9]+", " ", text.lower()).split()
    if len(words) > 1 and words[0] in IGNORED_LEADING_WORDS:
        words = words[1:]
    return " ".join(words)


def phonetic_key(text: str) -> str:
    """Reduce a normalized title to a rough sound-alike key."""
    for pattern, replacement in (
        (r"ph", "f"),
        (r"ck|c(?=[aouhlrk]|$)|q", "k"),
        (r"c", "s"),
        (r"z", "s"),
        (r"x", "ks"),
        (r"y", "i"),
        (r"(.)\1+", r"\1"),
        (r"ie\b", "i"),
        (r"e\b", ""),
    ):
        text = re.sub(pattern, replacement, text)
    return text


def title_score(query: str, title: str) -> float:
    """Return a 0..1 similarity between a normalized query and a title."""
    normalized = normalize_title(title)
    if not normalized or not query:
        return 0.0
    if normalized == query:
        return 1.0
    score = SequenceMatcher(None, query, normalized).ratio()
    score = max(
        score,
        0.95
        * SequenceMatcher(None, phonetic_key(query), phonetic_key(normalized)).ratio(),
    )
    if len(query) >= 4 and query in normalized:
        score = max(score, 0.85)
    elif len(normalized) >= 4 and normalized in query:
        score = max(score, 0.75)
    return score


def fuzzy_search(
    plex_server: PlexServer,
    query: str,
    mediatype: str | None = None,
    library_section: LibrarySection | None = None,
    limit: int = FUZZY_LIMIT,
) -> list[Any]:
    """Search Plex tolerating misspellings, best match first.

    Uses the Plex server search first. When that finds nothing, titles in the
    libraries are compared locally so near misses still produce results.
    """
    normalized_query = normalize_title(query)

    items: list[Any] = []
    if library_section is None:
        items = plex_server.search(query, mediatype=mediatype)
        items.sort(key=lambda x: title_score(normalized_query, x.title), reverse=True)
        if items and title_score(normalized_query, items[0].title) >= FUZZY_MIN_SCORE:
            return items

    sections = [library_section] if library_section else plex_server.library.sections()
    wanted_section_type = SECTION_TYPE_FOR_MEDIATYPE.get(mediatype or "")
    scored: list[tuple[float, Any]] = []
    for section in sections:
        if section.type not in SEARCHABLE_SECTION_TYPES:
            continue
        if wanted_section_type and section.type != wanted_section_type:
            continue
        candidates = section.search(libtype=mediatype) if mediatype else section.all()
        scored.extend(
            (score, candidate)
            for candidate in candidates
            if (score := title_score(normalized_query, candidate.title))
            >= FUZZY_MIN_SCORE
        )

    scored.sort(key=lambda x: x[0], reverse=True)
    fuzzy_items = [item for _, item in scored[:limit]]
    seen = {x.ratingKey for x in fuzzy_items}
    return fuzzy_items + [x for x in items if x.ratingKey not in seen]

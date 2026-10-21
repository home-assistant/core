"""Helper methods to search for Plex media."""

import logging
import re
from typing import TYPE_CHECKING, Any
import unicodedata

import jellyfish
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
# Types compared without a media type. Episodes and tracks are only compared
# when asked for, because listing all of them takes many requests.
DEFAULT_TYPES_BY_SECTION = {
    "movie": ("movie",),
    "show": ("show",),
    "artist": ("artist", "album"),
}
IGNORED_LEADING_WORDS = {"the", "a", "an"}
# Letters that Unicode normalization does not split into a base letter
FOLDED_LETTERS = str.maketrans(
    {"ø": "o", "æ": "ae", "œ": "oe", "ł": "l", "đ": "d", "ð": "d", "þ": "th"}
)


def normalize_title(text: str) -> str:
    """Normalize a title for comparison, ignoring case, accents and punctuation."""
    decomposed = unicodedata.normalize(
        "NFKD", text.casefold().translate(FOLDED_LETTERS)
    )
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    words = re.sub(r"[\W_]+", " ", stripped).split()
    if len(words) > 1 and words[0] in IGNORED_LEADING_WORDS:
        words = words[1:]
    return " ".join(words)


def _similarity(first: str, second: str) -> float:
    """Return a 0..1 similarity based on the number of edits between two texts."""
    if not first or not second:
        return 0.0
    return 1 - jellyfish.levenshtein_distance(first, second) / max(
        len(first), len(second)
    )


def _sorted_words(text: str) -> str:
    """Return the words of a text in alphabetical order."""
    return " ".join(sorted(text.split()))


def _sound_key(text: str) -> str:
    """Return a key that is the same for words that sound alike in English.

    Words without a sound, such as numbers or words in other scripts, stay as
    they are, so they must match exactly.
    """
    return " ".join(jellyfish.metaphone(word) or word for word in text.split())


def title_score(query: str, title: str) -> float:
    """Return a 0..1 similarity between a normalized query and a title."""
    normalized = normalize_title(title)
    if not normalized or not query:
        return 0.0
    if normalized == query:
        return 1.0
    spelling = _similarity(query, normalized)
    # Among titles that sound alike, the closer spelling scores higher
    sound = (
        0.95
        * _similarity(_sound_key(query), _sound_key(normalized))
        * (0.9 + 0.1 * spelling)
    )
    score = max(
        spelling,
        _similarity(_sorted_words(query), _sorted_words(normalized)),
        sound,
    )
    if len(query) >= 4 and query in normalized:
        score = max(score, 0.85)
    elif len(normalized) >= 4 and normalized in query:
        score = max(score, 0.75)
    return score


def _is_media(item: Any) -> bool:
    """Return if a search result is a media item with a title."""
    return hasattr(item, "title") and hasattr(item, "ratingKey")


def _rank(
    normalized_query: str, items: list[Any], min_score: float = 0.0
) -> list[tuple[float, Any]]:
    """Return the items with their score, best match first."""
    scored = [(title_score(normalized_query, item.title), item) for item in items]
    scored.sort(key=lambda scored_item: scored_item[0], reverse=True)
    return [(score, item) for score, item in scored if score >= min_score]


def fuzzy_search(
    plex_server: PlexServer,
    query: str,
    mediatype: str | None = None,
    library_section: LibrarySection | None = None,
    limit: int = FUZZY_LIMIT,
) -> list[Any]:
    """Search Plex tolerating misspellings, best match first.

    The search of Plex itself runs first, on the server or in the library.
    When it finds no good match, titles are compared locally so near misses
    still produce results.
    """
    normalized_query = normalize_title(query)

    try:
        if library_section is None:
            native = plex_server.search(query, mediatype=mediatype)
        else:
            native = library_section.search(title=query, libtype=mediatype)
    except BadRequest, NotFound:
        native = []
    ranked_native = _rank(normalized_query, [x for x in native if _is_media(x)])
    if ranked_native and ranked_native[0][0] >= FUZZY_MIN_SCORE:
        return [item for _, item in ranked_native]

    candidates: list[Any] = []
    if mediatype == "playlist":
        # Playlists belong to the server and are not listed in a library
        if library_section is None:
            candidates = list(plex_server.playlists())
    else:
        sections = (
            [library_section] if library_section else plex_server.library.sections()
        )
        wanted_section_type = SECTION_TYPE_FOR_MEDIATYPE.get(mediatype or "")
        for section in sections:
            if section.type not in DEFAULT_TYPES_BY_SECTION:
                continue
            if wanted_section_type and section.type != wanted_section_type:
                continue
            types = (
                (mediatype,) if mediatype else DEFAULT_TYPES_BY_SECTION[section.type]
            )
            for libtype in types:
                candidates.extend(section.search(libtype=libtype))

    matches = _rank(normalized_query, candidates, FUZZY_MIN_SCORE)[:limit]
    fuzzy_items = [item for _, item in matches]
    seen = {x.ratingKey for x in fuzzy_items}
    return fuzzy_items + [
        item for _, item in ranked_native if item.ratingKey not in seen
    ]


def find_media(
    plex_server: PlexServer,
    query: str,
    mediatype: str | None = None,
    library_section: LibrarySection | None = None,
    fuzzy: bool | None = None,
) -> list[Any]:
    """Search Plex by title, using the fuzzy search when enabled.

    When fuzzy is None the Plex integration option decides.
    """
    if fuzzy is None:
        fuzzy = plex_server.option_fuzzy_search
    if fuzzy:
        return fuzzy_search(plex_server, query, mediatype, library_section)
    if library_section is not None:
        return list(library_section.search(title=query, libtype=mediatype))
    return [x for x in plex_server.search(query, mediatype=mediatype) if _is_media(x)]

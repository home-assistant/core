"""Services for the Plex integration."""

from datetime import timedelta
import json
import logging
from typing import Any

from plexapi.exceptions import NotFound
import probatio
from yarl import URL

from homeassistant.components.http.auth import async_sign_path
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.template import result_as_boolean

from .const import (
    DOMAIN,
    PLEX_URI_SCHEME,
    SERVICE_ON_DECK,
    SERVICE_REFRESH_LIBRARY,
    SERVICE_SEARCH,
)
from .errors import MediaNotFound
from .helpers import get_plex_servers
from .media_browser import get_proxy_image_url
from .media_search import search_media
from .models import PlexMediaSearchResult
from .server import PlexServer

REFRESH_LIBRARY_SCHEMA = probatio.Schema(
    {probatio.Optional("server_name"): str, probatio.Required("library_name"): str}
)

SEARCH_FILTER_KEYS = (
    "title",
    "show_name",
    "season_number",
    "episode_name",
    "episode_number",
    "artist_name",
    "album_name",
    "track_name",
    "track_number",
    "year",
    "filters",
)

SEARCH_SCHEMA = probatio.All(
    probatio.Schema(
        {
            probatio.Optional("server_name"): str,
            probatio.Optional("username"): str,
            probatio.Optional("query"): str,
            probatio.Optional("plex_key"): int,
            probatio.Optional("playlist_name"): str,
            probatio.Optional("library_name"): str,
            probatio.Optional("media_type"): probatio.In(
                [
                    "movie",
                    "show",
                    "season",
                    "episode",
                    "artist",
                    "album",
                    "track",
                    "playlist",
                ]
            ),
            probatio.Optional("title"): str,
            probatio.Optional("show_name"): str,
            probatio.Optional("season_number"): int,
            probatio.Optional("episode_name"): str,
            probatio.Optional("episode_number"): int,
            probatio.Optional("artist_name"): str,
            probatio.Optional("album_name"): str,
            probatio.Optional("track_name"): str,
            probatio.Optional("track_number"): int,
            probatio.Optional("year"): int,
            probatio.Optional("filters"): dict,
            probatio.Optional("include_on_deck", default=False): bool,
        }
    ),
    probatio.AtLeastOne("query", "plex_key", "playlist_name", *SEARCH_FILTER_KEYS),
)

ON_DECK_SCHEMA = probatio.Schema(
    {
        probatio.Optional("server_name"): str,
        probatio.Optional("username"): str,
        probatio.Optional("library_name"): str,
        probatio.Optional("media_type"): probatio.In(["movie", "episode"]),
        probatio.Optional("limit", default=20): probatio.All(
            int, probatio.Range(min=1, max=100)
        ),
    }
)

# Signed links stop working at a restart, because the signing secret is lost
THUMBNAIL_URL_EXPIRATION = timedelta(days=365)

_LOGGER = logging.getLogger(__package__)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the Plex integration."""

    async def async_refresh_library_service(service_call: ServiceCall) -> None:
        await hass.async_add_executor_job(refresh_library, hass, service_call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_LIBRARY,
        async_refresh_library_service,
        schema=REFRESH_LIBRARY_SCHEMA,
    )

    async def async_search_service(service_call: ServiceCall) -> ServiceResponse:
        response = await hass.async_add_executor_job(
            search_plex_media, hass, service_call
        )
        _sign_thumbnails(hass, response)
        return response

    async def async_on_deck_service(service_call: ServiceCall) -> ServiceResponse:
        response = await hass.async_add_executor_job(
            get_on_deck_media, hass, service_call
        )
        _sign_thumbnails(hass, response)
        return response

    hass.services.async_register(
        DOMAIN,
        SERVICE_ON_DECK,
        async_on_deck_service,
        schema=ON_DECK_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH,
        async_search_service,
        schema=SEARCH_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


def refresh_library(hass: HomeAssistant, service_call: ServiceCall) -> None:
    """Scan a Plex library for new and updated media."""
    plex_server_name = service_call.data.get("server_name")
    library_name = service_call.data["library_name"]

    plex_server = get_plex_server(hass, plex_server_name)

    try:
        library = plex_server.library.section(title=library_name)
    except NotFound:
        _LOGGER.error(
            "Library with name '%s' not found in %s",
            library_name,
            [x.title for x in plex_server.library.sections()],
        )
        return

    _LOGGER.debug("Scanning %s for new and updated media", library_name)
    library.update()


def search_plex_media(hass: HomeAssistant, service_call: ServiceCall) -> dict[str, Any]:
    """Look up Plex media, accepting the same criteria as play_media."""
    data = dict(service_call.data)
    plex_server = get_plex_server(hass, data.pop("server_name", None))

    if username := data.pop("username", None):
        plex_server = _switch_user(plex_server, username)

    media_type = data.pop("media_type", None)
    library_name = data.pop("library_name", None)
    query = data.pop("query", None)
    plex_key = data.pop("plex_key", None)
    playlist_name = data.pop("playlist_name", None)
    include_on_deck = data.pop("include_on_deck", False)
    advanced_filters = data.pop("filters", None)
    filters = data

    results: list[Any]
    try:
        if plex_key is not None:
            results = [plex_server.fetch_item(plex_key)]
        elif playlist_name:
            results = [plex_server.playlist(playlist_name)]
        elif library_name:
            if query:
                filters.setdefault("title", query)
            results = _search_library(
                plex_server, library_name, media_type, filters, advanced_filters
            )
        elif filters or advanced_filters:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="library_required"
            )
        else:
            results = [
                x
                for x in plex_server.search(query, mediatype=media_type)
                if hasattr(x, "title") and hasattr(x, "ratingKey")
            ]
    except NotFound, MediaNotFound:
        results = []

    infos: list[dict[str, Any]] = []
    for item in results:
        info = _media_result_info(item, plex_server)
        if include_on_deck and item.type == "show":
            episode = item.onDeck()
            info["on_deck"] = (
                _media_result_info(episode, plex_server) if episode else None
            )
        infos.append(info)

    return {"results": infos}


def get_on_deck_media(hass: HomeAssistant, service_call: ServiceCall) -> dict[str, Any]:
    """Return unfinished and next up media from the Continue Watching hub."""
    data = service_call.data
    plex_server = get_plex_server(hass, data.get("server_name"))

    if username := data.get("username"):
        plex_server = _switch_user(plex_server, username)

    items = plex_server.continue_watching()
    if library_name := data.get("library_name"):
        items = [x for x in items if x.librarySectionTitle == library_name]
    if media_type := data.get("media_type"):
        items = [x for x in items if x.type == media_type]

    return {
        "results": [
            _media_result_info(item, plex_server) for item in items[: data["limit"]]
        ]
    }


def _switch_user(plex_server: PlexServer, username: str) -> PlexServer:
    """Return the Plex server as the given user."""
    try:
        return plex_server.switch_user(username)
    except NotFound as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="user_not_found",
            translation_placeholders={"user": username},
        ) from err


def _search_library(
    plex_server: PlexServer,
    library_name: str,
    media_type: str | None,
    filters: dict[str, Any],
    advanced_filters: dict[str, Any] | None,
) -> list[Any]:
    """Search a single library using play_media compatible filters."""
    try:
        library_section = plex_server.library.section(library_name)
    except NotFound as err:
        library_names = [x.title for x in plex_server.library.sections()]
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="library_not_found",
            translation_placeholders={
                "library": library_name,
                "libraries": ", ".join(library_names),
            },
        ) from err
    search_options: dict[str, Any] = {**filters, "allow_multiple": True}
    if advanced_filters:
        search_options["filters"] = advanced_filters
    if media_type:
        search_options["libtype"] = media_type
    results = search_media(
        search_options.get("libtype", ""), library_section, **search_options
    )
    return results if isinstance(results, list) else [results]


SEARCH_RESULT_ATTRIBUTES = {
    "year": "year",
    "summary": "summary",
    "tagline": "tagline",
    "studio": "studio",
    "content_rating": "contentRating",
    "rating": "rating",
    "audience_rating": "audienceRating",
    "duration": "duration",
    "view_count": "viewCount",
    "library_id": "librarySectionID",
    "library_name": "librarySectionTitle",
}

SEARCH_RESULT_TYPE_ATTRIBUTES = {
    "show": {
        "episode_count": "leafCount",
        "watched_episode_count": "viewedLeafCount",
        "season_count": "childCount",
    },
    "season": {
        "show_title": "parentTitle",
        "show_rating_key": "parentRatingKey",
        "show_guid": "parentGuid",
        "season_number": "index",
    },
    "episode": {
        "show_title": "grandparentTitle",
        "show_rating_key": "grandparentRatingKey",
        "show_guid": "grandparentGuid",
        "season_title": "parentTitle",
        "season_rating_key": "parentRatingKey",
        "season_guid": "parentGuid",
        "season_number": "parentIndex",
        "episode_number": "index",
    },
    "album": {"artist_name": "parentTitle"},
    "track": {
        "artist_name": "grandparentTitle",
        "album_title": "parentTitle",
        "track_number": "index",
    },
}

SEARCH_RESULT_DATES = {
    "originally_available_at": "originallyAvailableAt",
    "added_at": "addedAt",
    "last_viewed_at": "lastViewedAt",
}


def _proxy_thumb_url(item: Any, plex_server: PlexServer) -> str | None:
    """Return the Home Assistant proxy path of a thumbnail, without the Plex token."""
    if not (thumb_url := getattr(item, "thumbUrl", None)):
        return None
    plex_server.thumbnail_cache.setdefault(str(item.ratingKey), thumb_url)
    return get_proxy_image_url(plex_server.machine_identifier, item.ratingKey)


@callback
def _sign_thumbnails(hass: HomeAssistant, response: dict[str, Any]) -> None:
    """Sign the thumbnail paths of a response.

    Signing initializes a shared secret, so it runs on the event loop.
    """
    for info in response["results"]:
        for entry in (info, info.get("on_deck")):
            if entry and (path := entry.get("thumb_path")):
                entry["thumb_url"] = async_sign_path(
                    hass, path, THUMBNAIL_URL_EXPIRATION, use_content_user=True
                )


def _media_result_info(item: Any, plex_server: PlexServer) -> dict[str, Any]:
    """Return info for a Plex media item, usable in automations (e.g. deep links)."""
    info: dict[str, Any] = {
        "title": item.title,
        "media_type": item.type,
        "guid": item.guid,
        "rating_key": item.ratingKey,
        "key": item.key,
        "thumb_path": _proxy_thumb_url(item, plex_server),
        "thumb_url": None,
        "server_id": plex_server.machine_identifier,
        "server_name": plex_server.friendly_name,
    }
    attributes = {
        **SEARCH_RESULT_ATTRIBUTES,
        **SEARCH_RESULT_TYPE_ATTRIBUTES.get(item.type, {}),
    }
    for name, attribute in attributes.items():
        info[name] = getattr(item, attribute, None)
    for name, attribute in SEARCH_RESULT_DATES.items():
        value = getattr(item, attribute, None)
        info[name] = value.isoformat() if value else None
    info["genres"] = [x.tag for x in getattr(item, "genres", None) or []]
    info["is_watched"] = getattr(item, "isPlayed", None)
    view_offset = getattr(item, "viewOffset", None)
    duration = info["duration"]
    info["view_offset"] = view_offset
    info["progress_percent"] = (
        round(view_offset / duration * 100)
        if view_offset is not None and duration
        else None
    )
    return info


def get_plex_server(
    hass: HomeAssistant,
    plex_server_name: str | None = None,
    plex_server_id: str | None = None,
) -> PlexServer:
    """Retrieve a configured Plex server by name."""
    if DOMAIN not in hass.data:
        raise HomeAssistantError("Plex integration not configured")
    servers = get_plex_servers(hass)
    if not servers:
        raise HomeAssistantError("No Plex servers available")

    if plex_server_id:
        return servers[plex_server_id]

    plex_servers = servers.values()
    if plex_server_name:
        plex_server = next(
            (x for x in plex_servers if x.friendly_name == plex_server_name), None
        )
        if plex_server is not None:
            return plex_server
        friendly_names = [x.friendly_name for x in plex_servers]
        raise HomeAssistantError(
            f"Requested Plex server '{plex_server_name}' not found in {friendly_names}"
        )

    if len(plex_servers) == 1:
        return next(iter(plex_servers))

    friendly_names = [x.friendly_name for x in plex_servers]
    raise HomeAssistantError(
        "Multiple Plex servers configured, choose with 'plex_server' key:"
        f" {friendly_names}"
    )


def process_plex_payload(
    hass: HomeAssistant,
    content_type: str,
    content_id: str,
    default_plex_server: PlexServer | None = None,
    supports_playqueues: bool = True,
) -> PlexMediaSearchResult:
    """Look up Plex media using media_player.play_media service payloads."""
    plex_server = default_plex_server
    extra_params = {}

    if content_id.startswith(PLEX_URI_SCHEME + "{"):
        # Handle the special payload of 'plex://{<json>}'
        content_id = content_id.removeprefix(PLEX_URI_SCHEME)
        content = json.loads(content_id)
    elif content_id.startswith(PLEX_URI_SCHEME):
        # Handle standard media_browser payloads
        plex_url = URL(content_id)
        # https://github.com/pylint-dev/pylint/issues/3484
        # pylint: disable-next=using-constant-test
        if plex_url.name:
            if len(plex_url.parts) == 2:
                if plex_url.name == "search":
                    content = {}
                else:
                    content = int(plex_url.name)
            else:
                # For "special" items like radio stations
                content = plex_url.path
            server_id = plex_url.host
            plex_server = get_plex_server(hass, plex_server_id=server_id)
        else:  # noqa: PLR5501
            # Handle legacy payloads without server_id in URL host position
            if plex_url.host == "search":
                content = {}
            else:
                content = int(plex_url.host)  # type: ignore[arg-type]
        extra_params = dict(plex_url.query)
    else:
        content = json.loads(content_id)

    if isinstance(content, dict):
        if plex_server_name := content.pop("plex_server", None):
            plex_server = get_plex_server(hass, plex_server_name)

    if not plex_server:
        plex_server = get_plex_server(hass)

    if isinstance(content, dict):
        if plex_user := content.pop("username", None):
            _LOGGER.debug("Switching to Plex user: %s", plex_user)
            plex_server = plex_server.switch_user(plex_user)

    if content_type == "station":
        if not supports_playqueues:
            raise HomeAssistantError("Plex stations are not supported on this device")
        playqueue = plex_server.create_station_playqueue(content)
        return PlexMediaSearchResult(playqueue)

    if isinstance(content, int):
        content = {"plex_key": content}
        content_type = DOMAIN

    content.update(extra_params)

    if playqueue_id := content.pop("playqueue_id", None):
        if not supports_playqueues:
            raise HomeAssistantError("Plex playqueues are not supported on this device")
        try:
            playqueue = plex_server.get_playqueue(playqueue_id)
        except NotFound as err:
            raise MediaNotFound(
                f"PlayQueue '{playqueue_id}' could not be found"
            ) from err
        return PlexMediaSearchResult(playqueue, content)

    search_query = content.copy()
    shuffle = search_query.pop("shuffle", 0)
    continuous = search_query.pop("continuous", 0)

    # Remove internal kwargs before passing copy to plexapi
    for internal_key in ("resume", "offset"):
        search_query.pop(internal_key, None)

    media = plex_server.lookup_media(content_type, **search_query)

    resume = content.get("resume", False)
    if isinstance(resume, str):
        resume = result_as_boolean(resume)
    if resume and getattr(media, "type", None) == "show":
        if (on_deck := media.onDeck()) is not None:
            media = on_deck
        else:
            content["resume"] = False

    if supports_playqueues and (isinstance(media, list) or shuffle or continuous):
        playqueue = plex_server.create_playqueue(
            media,
            includeRelated=0,
            shuffle=1 if shuffle else 0,
            continuous=1 if continuous else 0,
        )
        return PlexMediaSearchResult(playqueue, content)

    return PlexMediaSearchResult(media, content)

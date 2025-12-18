"""Custom actions (previously known as services) for the Music Assistant integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from music_assistant_models.enums import MediaType, QueueOption
import voluptuous as vol

from homeassistant.components.media_player import (
    ATTR_MEDIA_ENQUEUE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
)
from homeassistant.const import ATTR_CONFIG_ENTRY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import (
    ATTR_ALBUM,
    ATTR_ALBUM_ARTISTS_ONLY,
    ATTR_ALBUM_TYPE,
    ATTR_ALBUMS,
    ATTR_ANNOUNCE_VOLUME,
    ATTR_ARTIST,
    ATTR_ARTISTS,
    ATTR_AUDIOBOOKS,
    ATTR_AUTO_PLAY,
    ATTR_FAVORITE,
    ATTR_ITEMS,
    ATTR_LIBRARY_ONLY,
    ATTR_LIMIT,
    ATTR_MEDIA_ID,
    ATTR_MEDIA_TYPE,
    ATTR_OFFSET,
    ATTR_ORDER_BY,
    ATTR_PLAYLISTS,
    ATTR_PODCASTS,
    ATTR_RADIO,
    ATTR_RADIO_MODE,
    ATTR_SEARCH,
    ATTR_SEARCH_ALBUM,
    ATTR_SEARCH_ARTIST,
    ATTR_SEARCH_NAME,
    ATTR_SOURCE_PLAYER,
    ATTR_TRACKS,
    ATTR_URL,
    ATTR_USE_PRE_ANNOUNCE,
    DOMAIN,
)
from .helpers import get_music_assistant_client
from .schemas import (
    LIBRARY_RESULTS_SCHEMA,
    SEARCH_RESULT_SCHEMA,
    media_item_dict_from_mass_item,
)

if TYPE_CHECKING:
    from music_assistant_models.media_items import (
        Album,
        Artist,
        Audiobook,
        Playlist,
        Podcast,
        Radio,
        Track,
    )

SERVICE_SEARCH = "search"
SERVICE_GET_LIBRARY = "get_library"
SERVICE_PLAY_MEDIA_ADVANCED = "play_media"
SERVICE_PLAY_ANNOUNCEMENT = "play_announcement"
SERVICE_TRANSFER_QUEUE = "transfer_queue"
SERVICE_GET_QUEUE = "get_queue"

DEFAULT_OFFSET = 0
DEFAULT_LIMIT = 25
DEFAULT_SORT_ORDER = "name"


@callback
def register_actions(hass: HomeAssistant) -> None:
    """Register custom actions."""
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH,
        handle_search,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY_ID): str,
                vol.Required(ATTR_SEARCH_NAME): cv.string,
                vol.Optional(ATTR_MEDIA_TYPE): vol.All(
                    cv.ensure_list, [vol.Coerce(MediaType)]
                ),
                vol.Optional(ATTR_SEARCH_ARTIST): cv.string,
                vol.Optional(ATTR_SEARCH_ALBUM): cv.string,
                vol.Optional(ATTR_LIMIT, default=5): vol.Coerce(int),
                vol.Optional(ATTR_LIBRARY_ONLY, default=False): cv.boolean,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_LIBRARY,
        handle_get_library,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CONFIG_ENTRY_ID): str,
                vol.Required(ATTR_MEDIA_TYPE): vol.Coerce(MediaType),
                vol.Optional(ATTR_FAVORITE): cv.boolean,
                vol.Optional(ATTR_SEARCH): cv.string,
                vol.Optional(ATTR_LIMIT): cv.positive_int,
                vol.Optional(ATTR_OFFSET): int,
                vol.Optional(ATTR_ORDER_BY): cv.string,
                vol.Optional(ATTR_ALBUM_TYPE): list[MediaType],
                vol.Optional(ATTR_ALBUM_ARTISTS_ONLY): cv.boolean,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    # Platform entity services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_PLAY_MEDIA_ADVANCED,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            vol.Required(ATTR_MEDIA_ID): vol.All(cv.ensure_list, [cv.string]),
            vol.Optional(ATTR_MEDIA_TYPE): vol.Coerce(MediaType),
            vol.Optional(ATTR_MEDIA_ENQUEUE): vol.Coerce(QueueOption),
            vol.Optional(ATTR_ARTIST): cv.string,
            vol.Optional(ATTR_ALBUM): cv.string,
            vol.Optional(ATTR_RADIO_MODE): vol.Coerce(bool),
        },
        func="_async_handle_play_media",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_PLAY_ANNOUNCEMENT,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            vol.Required(ATTR_URL): cv.string,
            vol.Optional(ATTR_USE_PRE_ANNOUNCE): vol.Coerce(bool),
            vol.Optional(ATTR_ANNOUNCE_VOLUME): vol.Coerce(int),
        },
        func="_async_handle_play_announcement",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_TRANSFER_QUEUE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema={
            vol.Optional(ATTR_SOURCE_PLAYER): cv.entity_id,
            vol.Optional(ATTR_AUTO_PLAY): vol.Coerce(bool),
        },
        func="_async_handle_transfer_queue",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        SERVICE_GET_QUEUE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        schema=None,
        func="_async_handle_get_queue",
        supports_response=SupportsResponse.ONLY,
    )


async def handle_search(call: ServiceCall) -> ServiceResponse:
    """Handle queue_command action."""
    mass = get_music_assistant_client(call.hass, call.data[ATTR_CONFIG_ENTRY_ID])
    search_name = call.data[ATTR_SEARCH_NAME]
    search_artist = call.data.get(ATTR_SEARCH_ARTIST)
    search_album = call.data.get(ATTR_SEARCH_ALBUM)
    if search_album and search_artist:
        search_name = f"{search_artist} - {search_album} - {search_name}"
    elif search_album:
        search_name = f"{search_album} - {search_name}"
    elif search_artist:
        search_name = f"{search_artist} - {search_name}"
    search_results = await mass.music.search(
        search_query=search_name,
        media_types=call.data.get(ATTR_MEDIA_TYPE, MediaType.ALL),
        limit=call.data[ATTR_LIMIT],
        library_only=call.data[ATTR_LIBRARY_ONLY],
    )
    response: ServiceResponse = SEARCH_RESULT_SCHEMA(
        {
            ATTR_ARTISTS: [
                media_item_dict_from_mass_item(mass, item)
                for item in search_results.artists
            ],
            ATTR_ALBUMS: [
                media_item_dict_from_mass_item(mass, item)
                for item in search_results.albums
            ],
            ATTR_TRACKS: [
                media_item_dict_from_mass_item(mass, item)
                for item in search_results.tracks
            ],
            ATTR_PLAYLISTS: [
                media_item_dict_from_mass_item(mass, item)
                for item in search_results.playlists
            ],
            ATTR_RADIO: [
                media_item_dict_from_mass_item(mass, item)
                for item in search_results.radio
            ],
            ATTR_AUDIOBOOKS: [
                media_item_dict_from_mass_item(mass, item)
                for item in search_results.audiobooks
            ],
            ATTR_PODCASTS: [
                media_item_dict_from_mass_item(mass, item)
                for item in search_results.podcasts
            ],
        }
    )
    return response


async def handle_get_library(call: ServiceCall) -> ServiceResponse:
    """Handle get_library action."""
    mass = get_music_assistant_client(call.hass, call.data[ATTR_CONFIG_ENTRY_ID])
    media_type = call.data[ATTR_MEDIA_TYPE]
    limit = call.data.get(ATTR_LIMIT, DEFAULT_LIMIT)
    offset = call.data.get(ATTR_OFFSET, DEFAULT_OFFSET)
    order_by = call.data.get(ATTR_ORDER_BY, DEFAULT_SORT_ORDER)
    base_params = {
        "favorite": call.data.get(ATTR_FAVORITE),
        "search": call.data.get(ATTR_SEARCH),
        "limit": limit,
        "offset": offset,
        "order_by": order_by,
    }
    library_result: (
        list[Album]
        | list[Artist]
        | list[Track]
        | list[Radio]
        | list[Playlist]
        | list[Audiobook]
        | list[Podcast]
    )
    if media_type == MediaType.ALBUM:
        library_result = await mass.music.get_library_albums(
            **base_params,
            album_types=call.data.get(ATTR_ALBUM_TYPE),
        )
    elif media_type == MediaType.ARTIST:
        library_result = await mass.music.get_library_artists(
            **base_params,
            album_artists_only=bool(call.data.get(ATTR_ALBUM_ARTISTS_ONLY)),
        )
    elif media_type == MediaType.TRACK:
        library_result = await mass.music.get_library_tracks(
            **base_params,
        )
    elif media_type == MediaType.RADIO:
        library_result = await mass.music.get_library_radios(
            **base_params,
        )
    elif media_type == MediaType.PLAYLIST:
        library_result = await mass.music.get_library_playlists(
            **base_params,
        )
    elif media_type == MediaType.AUDIOBOOK:
        library_result = await mass.music.get_library_audiobooks(
            **base_params,
        )
    elif media_type == MediaType.PODCAST:
        library_result = await mass.music.get_library_podcasts(
            **base_params,
        )
    else:
        raise ServiceValidationError(f"Unsupported media type {media_type}")

    response: ServiceResponse = LIBRARY_RESULTS_SCHEMA(
        {
            ATTR_ITEMS: [
                media_item_dict_from_mass_item(mass, item) for item in library_result
            ],
            ATTR_LIMIT: limit,
            ATTR_OFFSET: offset,
            ATTR_ORDER_BY: order_by,
            ATTR_MEDIA_TYPE: media_type,
        }
    )
    return response

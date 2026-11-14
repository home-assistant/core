"""Custom actions (previously known as services) for the Music Assistant integration."""

from enum import StrEnum
from typing import TYPE_CHECKING

from music_assistant_models.enums import MediaType, QueueOption
import probatio

from homeassistant.components.media_player import (
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    MediaPlayerDeviceClass,
)
from homeassistant.components.tts import DOMAIN as TTS_DOMAIN
from homeassistant.const import CommonServiceArgument
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
    ATTR_ALBUMS,
    ATTR_ARTISTS,
    ATTR_AUDIOBOOKS,
    ATTR_ITEMS,
    ATTR_LIMIT,
    ATTR_MEDIA_TYPE,
    ATTR_OFFSET,
    ATTR_ORDER_BY,
    ATTR_PLAYLISTS,
    ATTR_PODCASTS,
    ATTR_RADIO,
    ATTR_TRACKS,
    DOMAIN,
)
from .helpers import catch_user_not_found, get_music_assistant_client, user_from_context
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


DEFAULT_OFFSET = 0
DEFAULT_LIMIT = 25
DEFAULT_SORT_ORDER = "name"

# player-only entity services; dashboard display entities don't implement them
PLAYER_ENTITY_DEVICE_CLASSES = [MediaPlayerDeviceClass.SPEAKER]


class MusicAssistantService(StrEnum):
    """Store keys for Music Assistant services."""

    PLAY_MEDIA = "play_media"
    PLAY_ANNOUNCEMENT = "play_announcement"
    TRANSFER_QUEUE = "transfer_queue"
    GET_QUEUE = "get_queue"
    SEARCH = "search"
    GET_LIBRARY = "get_library"


class MusicAssistantServiceArgument(StrEnum):
    """Store keys for Music Assistant service arguments."""

    MEDIA_ID = "media_id"
    MEDIA_TYPE = "media_type"
    ARTIST = "artist"
    ALBUM = "album"
    ENQUEUE = "enqueue"
    RADIO_MODE = "radio_mode"
    SHUFFLE = "shuffle"
    START_ITEM = "start_item"
    USERNAME = "username"
    MESSAGE = "message"
    TTS_ENTITY_ID = "tts_entity_id"
    URL = "url"
    USE_PRE_ANNOUNCE = "use_pre_announce"
    PRE_ANNOUNCE_URL = "pre_announce_url"
    ANNOUNCE_VOLUME = "announce_volume"
    SOURCE_PLAYER = "source_player"
    AUTO_PLAY = "auto_play"
    NAME = "name"
    LIMIT = "limit"
    LIBRARY_ONLY = "library_only"
    FAVORITE = "favorite"
    SEARCH = "search"
    OFFSET = "offset"
    ORDER_BY = "order_by"
    ALBUM_TYPE = "album_type"
    ALBUM_ARTISTS_ONLY = "album_artists_only"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register custom actions."""
    hass.services.async_register(
        DOMAIN,
        MusicAssistantService.SEARCH,
        handle_search,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): str,
                probatio.Required(MusicAssistantServiceArgument.NAME): cv.string,
                probatio.Optional(
                    MusicAssistantServiceArgument.MEDIA_TYPE
                ): probatio.All(probatio.EnsureList(), [probatio.Coerce(MediaType)]),
                probatio.Optional(MusicAssistantServiceArgument.ARTIST): cv.string,
                probatio.Optional(MusicAssistantServiceArgument.ALBUM): cv.string,
                probatio.Optional(
                    MusicAssistantServiceArgument.LIMIT, default=5
                ): probatio.Coerce(int),
                probatio.Optional(
                    MusicAssistantServiceArgument.LIBRARY_ONLY, default=False
                ): cv.boolean,
                probatio.Optional(MusicAssistantServiceArgument.USERNAME): cv.string,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        MusicAssistantService.GET_LIBRARY,
        handle_get_library,
        schema=probatio.Schema(
            {
                probatio.Required(CommonServiceArgument.CONFIG_ENTRY_ID): str,
                probatio.Required(
                    MusicAssistantServiceArgument.MEDIA_TYPE
                ): probatio.Coerce(MediaType),
                probatio.Optional(MusicAssistantServiceArgument.FAVORITE): cv.boolean,
                probatio.Optional(MusicAssistantServiceArgument.SEARCH): cv.string,
                probatio.Optional(MusicAssistantServiceArgument.LIMIT): cv.positive_int,
                probatio.Optional(MusicAssistantServiceArgument.OFFSET): int,
                probatio.Optional(MusicAssistantServiceArgument.ORDER_BY): cv.string,
                probatio.Optional(MusicAssistantServiceArgument.ALBUM_TYPE): list[
                    MediaType
                ],
                probatio.Optional(
                    MusicAssistantServiceArgument.ALBUM_ARTISTS_ONLY
                ): cv.boolean,
                probatio.Optional(MusicAssistantServiceArgument.USERNAME): cv.string,
            }
        ),
        supports_response=SupportsResponse.ONLY,
    )

    # Platform entity services
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MusicAssistantService.PLAY_MEDIA,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        entity_device_classes=PLAYER_ENTITY_DEVICE_CLASSES,
        schema={
            probatio.Required(MusicAssistantServiceArgument.MEDIA_ID): probatio.All(
                probatio.EnsureList(), [cv.string]
            ),
            probatio.Optional(
                MusicAssistantServiceArgument.MEDIA_TYPE
            ): probatio.Coerce(MediaType),
            probatio.Optional(MusicAssistantServiceArgument.ENQUEUE): probatio.Coerce(
                QueueOption
            ),
            probatio.Optional(MusicAssistantServiceArgument.ARTIST): cv.string,
            probatio.Optional(MusicAssistantServiceArgument.ALBUM): cv.string,
            probatio.Optional(
                MusicAssistantServiceArgument.RADIO_MODE
            ): probatio.Coerce(bool),
            probatio.Optional(MusicAssistantServiceArgument.SHUFFLE): cv.boolean,
            probatio.Optional(MusicAssistantServiceArgument.START_ITEM): cv.string,
            probatio.Optional(MusicAssistantServiceArgument.USERNAME): cv.string,
        },
        func="_async_handle_play_media",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MusicAssistantService.PLAY_ANNOUNCEMENT,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        entity_device_classes=PLAYER_ENTITY_DEVICE_CLASSES,
        schema=probatio.All(
            cv.make_entity_service_schema(
                {
                    probatio.Optional(MusicAssistantServiceArgument.URL): cv.string,
                    probatio.Inclusive(
                        MusicAssistantServiceArgument.MESSAGE, "spoken_announcement"
                    ): cv.string,
                    probatio.Inclusive(
                        MusicAssistantServiceArgument.TTS_ENTITY_ID,
                        "spoken_announcement",
                    ): probatio.All(cv.entity_id, cv.entity_domain(TTS_DOMAIN)),
                    probatio.Optional(
                        MusicAssistantServiceArgument.USE_PRE_ANNOUNCE
                    ): probatio.Coerce(bool),
                    probatio.Optional(
                        MusicAssistantServiceArgument.PRE_ANNOUNCE_URL
                    ): cv.string,
                    probatio.Optional(
                        MusicAssistantServiceArgument.ANNOUNCE_VOLUME
                    ): probatio.Coerce(int),
                }
            ),
            probatio.AtLeastOne(
                MusicAssistantServiceArgument.URL, MusicAssistantServiceArgument.MESSAGE
            ),
            probatio.AtMostOne(
                MusicAssistantServiceArgument.URL, MusicAssistantServiceArgument.MESSAGE
            ),
        ),
        func="_async_handle_play_announcement",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MusicAssistantService.TRANSFER_QUEUE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        entity_device_classes=PLAYER_ENTITY_DEVICE_CLASSES,
        schema={
            probatio.Optional(
                MusicAssistantServiceArgument.SOURCE_PLAYER
            ): cv.entity_id,
            probatio.Optional(MusicAssistantServiceArgument.AUTO_PLAY): probatio.Coerce(
                bool
            ),
        },
        func="_async_handle_transfer_queue",
    )
    service.async_register_platform_entity_service(
        hass,
        DOMAIN,
        MusicAssistantService.GET_QUEUE,
        entity_domain=MEDIA_PLAYER_DOMAIN,
        entity_device_classes=PLAYER_ENTITY_DEVICE_CLASSES,
        schema=None,
        func="_async_handle_get_queue",
        supports_response=SupportsResponse.ONLY,
    )


async def handle_search(call: ServiceCall) -> ServiceResponse:
    """Handle queue_command action."""
    mass = get_music_assistant_client(
        call.hass, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )
    search_name = call.data[MusicAssistantServiceArgument.NAME]
    search_artist = call.data.get(MusicAssistantServiceArgument.ARTIST)
    search_album = call.data.get(MusicAssistantServiceArgument.ALBUM)
    search_username = call.data.get(MusicAssistantServiceArgument.USERNAME)
    if search_album and search_artist:
        search_name = f"{search_artist} - {search_album} - {search_name}"
    elif search_album:
        search_name = f"{search_album} - {search_name}"
    elif search_artist:
        search_name = f"{search_artist} - {search_name}"
    with catch_user_not_found(search_username):
        search_results = await mass.music.search(
            search_query=search_name,
            media_types=call.data.get(
                MusicAssistantServiceArgument.MEDIA_TYPE, MediaType.ALL
            ),
            limit=call.data[MusicAssistantServiceArgument.LIMIT],
            library_only=call.data[MusicAssistantServiceArgument.LIBRARY_ONLY],
            user=search_username
            if search_username is not None
            else user_from_context(call.context),
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
    mass = get_music_assistant_client(
        call.hass, call.data[CommonServiceArgument.CONFIG_ENTRY_ID]
    )
    media_type = call.data[MusicAssistantServiceArgument.MEDIA_TYPE]
    limit = call.data.get(MusicAssistantServiceArgument.LIMIT, DEFAULT_LIMIT)
    offset = call.data.get(MusicAssistantServiceArgument.OFFSET, DEFAULT_OFFSET)
    order_by = call.data.get(MusicAssistantServiceArgument.ORDER_BY, DEFAULT_SORT_ORDER)
    username = call.data.get(MusicAssistantServiceArgument.USERNAME)
    base_params = {
        "favorite": call.data.get(MusicAssistantServiceArgument.FAVORITE),
        "search": call.data.get(MusicAssistantServiceArgument.SEARCH),
        "limit": limit,
        "offset": offset,
        "order_by": order_by,
        "user": username,
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
    with catch_user_not_found(username):
        if media_type == MediaType.ALBUM:
            library_result = await mass.music.get_library_albums(
                **base_params,
                album_types=call.data.get(MusicAssistantServiceArgument.ALBUM_TYPE),
            )
        elif media_type == MediaType.ARTIST:
            library_result = await mass.music.get_library_artists(
                **base_params,
                album_artists_only=bool(
                    call.data.get(MusicAssistantServiceArgument.ALBUM_ARTISTS_ONLY)
                ),
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

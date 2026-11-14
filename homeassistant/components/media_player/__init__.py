"""Component to interface with various media players."""

import datetime as dt
from http import HTTPStatus
import logging
from typing import Any

from aiohttp import hdrs, web
from aiohttp.hdrs import CACHE_CONTROL
from aiohttp.typedefs import LooseHeaders
import probatio

from homeassistant.components import websocket_api
from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.components.websocket_api import ERR_NOT_SUPPORTED, ERR_UNKNOWN_ERROR
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_PICTURE,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_MEDIA_STOP,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_IDLE,
    STATE_OFF,
    STATE_PLAYING,
    STATE_STANDBY,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.typing import ConfigType

from .browse_media import (
    BrowseMedia,
    SearchMedia,
    SearchMediaQuery,
    async_process_play_media_url,
)
from .const import (
    ATTR_APP_ID,
    ATTR_APP_NAME,
    ATTR_ENTITY_PICTURE_LOCAL,
    ATTR_GROUP_MEMBERS,
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA,
    ATTR_MEDIA_ALBUM_ARTIST,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ANNOUNCE,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_CHANNEL,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_EPISODE,
    ATTR_MEDIA_EXTRA,
    ATTR_MEDIA_FILTER_CLASSES,
    ATTR_MEDIA_PLAYLIST,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEARCH_QUERY,
    ATTR_MEDIA_SEASON,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SERIES_TITLE,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_TRACK,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    ATTR_SOUND_MODE,
    ATTR_SOUND_MODE_LIST,
    CONTENT_AUTH_EXPIRY_TIME,
    DATA_COMPONENT,
    DEVICE_CLASSES_SCHEMA,
    DOMAIN,
    INTENT_MEDIA_SEARCH_AND_PLAY,
    MEDIA_PLAYER_PLAY_MEDIA_SCHEMA,
    REPEAT_MODES,
    SERVICE_BROWSE_MEDIA,
    SERVICE_CLEAR_PLAYLIST,
    SERVICE_JOIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SEARCH_MEDIA,
    SERVICE_SELECT_SOUND_MODE,
    SERVICE_SELECT_SOURCE,
    SERVICE_UNJOIN,
    MediaClass,
    MediaPlayerDeviceClass,
    MediaPlayerEnqueue,
    MediaPlayerEntityCapabilityAttribute,
    MediaPlayerEntityFeature,
    MediaPlayerEntityStateAttribute,
    MediaPlayerService,
    MediaPlayerServiceArgument,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from .entity import MediaPlayerEntity, MediaPlayerEntityDescription, async_fetch_image
from .errors import BrowseError, SearchError
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"
PLATFORM_SCHEMA = cv.PLATFORM_SCHEMA
PLATFORM_SCHEMA_BASE = cv.PLATFORM_SCHEMA_BASE
SCAN_INTERVAL = dt.timedelta(seconds=10)


DEVICE_CLASSES = [cls.value for cls in MediaPlayerDeviceClass]


MEDIA_PLAYER_BROWSE_MEDIA_SCHEMA = {
    probatio.Optional(ATTR_MEDIA_CONTENT_TYPE): cv.string,
    probatio.Optional(ATTR_MEDIA_CONTENT_ID): cv.string,
}


__all__ = [
    "ATTR_APP_ID",
    "ATTR_APP_NAME",
    "ATTR_ENTITY_PICTURE",
    "ATTR_ENTITY_PICTURE_LOCAL",
    "ATTR_GROUP_MEMBERS",
    "ATTR_INPUT_SOURCE",
    "ATTR_INPUT_SOURCE_LIST",
    "ATTR_MEDIA",
    "ATTR_MEDIA_ALBUM_ARTIST",
    "ATTR_MEDIA_ALBUM_NAME",
    "ATTR_MEDIA_ANNOUNCE",
    "ATTR_MEDIA_ARTIST",
    "ATTR_MEDIA_CHANNEL",
    "ATTR_MEDIA_CONTENT_ID",
    "ATTR_MEDIA_CONTENT_TYPE",
    "ATTR_MEDIA_DURATION",
    "ATTR_MEDIA_ENQUEUE",
    "ATTR_MEDIA_EPISODE",
    "ATTR_MEDIA_EXTRA",
    "ATTR_MEDIA_FILTER_CLASSES",
    "ATTR_MEDIA_PLAYLIST",
    "ATTR_MEDIA_POSITION",
    "ATTR_MEDIA_POSITION_UPDATED_AT",
    "ATTR_MEDIA_REPEAT",
    "ATTR_MEDIA_SEARCH_QUERY",
    "ATTR_MEDIA_SEASON",
    "ATTR_MEDIA_SEEK_POSITION",
    "ATTR_MEDIA_SERIES_TITLE",
    "ATTR_MEDIA_SHUFFLE",
    "ATTR_MEDIA_TITLE",
    "ATTR_MEDIA_TRACK",
    "ATTR_MEDIA_VOLUME_LEVEL",
    "ATTR_MEDIA_VOLUME_MUTED",
    "ATTR_SOUND_MODE",
    "ATTR_SOUND_MODE_LIST",
    "CONTENT_AUTH_EXPIRY_TIME",
    "DEVICE_CLASSES_SCHEMA",
    "DOMAIN",
    "ENTITY_ID_FORMAT",
    "INTENT_MEDIA_SEARCH_AND_PLAY",
    "MEDIA_PLAYER_PLAY_MEDIA_SCHEMA",
    "PLATFORM_SCHEMA",
    "PLATFORM_SCHEMA_BASE",
    "REPEAT_MODES",
    "SERVICE_BROWSE_MEDIA",
    "SERVICE_CLEAR_PLAYLIST",
    "SERVICE_JOIN",
    "SERVICE_MEDIA_NEXT_TRACK",
    "SERVICE_MEDIA_PAUSE",
    "SERVICE_MEDIA_PLAY",
    "SERVICE_MEDIA_PLAY_PAUSE",
    "SERVICE_MEDIA_PREVIOUS_TRACK",
    "SERVICE_MEDIA_SEEK",
    "SERVICE_MEDIA_STOP",
    "SERVICE_PLAY_MEDIA",
    "SERVICE_REPEAT_SET",
    "SERVICE_SEARCH_MEDIA",
    "SERVICE_SELECT_SOUND_MODE",
    "SERVICE_SELECT_SOURCE",
    "SERVICE_SHUFFLE_SET",
    "SERVICE_TOGGLE",
    "SERVICE_TURN_OFF",
    "SERVICE_TURN_ON",
    "SERVICE_UNJOIN",
    "SERVICE_VOLUME_DOWN",
    "SERVICE_VOLUME_MUTE",
    "SERVICE_VOLUME_SET",
    "SERVICE_VOLUME_UP",
    "STATE_IDLE",
    "STATE_OFF",
    "STATE_PLAYING",
    "STATE_STANDBY",
    "BrowseError",
    "BrowseMedia",
    "MediaClass",
    "MediaPlayerDeviceClass",
    "MediaPlayerEnqueue",
    "MediaPlayerEntity",
    "MediaPlayerEntityCapabilityAttribute",
    "MediaPlayerEntityDescription",
    "MediaPlayerEntityFeature",
    "MediaPlayerEntityStateAttribute",
    "MediaPlayerService",
    "MediaPlayerServiceArgument",
    "MediaPlayerState",
    "MediaType",
    "RepeatMode",
    "SearchError",
    "SearchMedia",
    "SearchMediaQuery",
    "async_fetch_image",
    "async_process_play_media_url",
]

# mypy: disallow-any-generics


def is_on(hass: HomeAssistant, entity_id: str | None = None) -> bool:
    """Return true if specified media player entity_id is on.

    Check all media player if no entity_id specified.
    """
    entity_ids = [entity_id] if entity_id else hass.states.entity_ids(DOMAIN)
    return any(
        not hass.states.is_state(entity_id, MediaPlayerState.OFF)
        for entity_id in entity_ids
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Track states and offer events for media_players."""
    component = hass.data[DATA_COMPONENT] = EntityComponent[MediaPlayerEntity](
        logging.getLogger(__name__), DOMAIN, hass, SCAN_INTERVAL
    )

    websocket_api.async_register_command(hass, websocket_browse_media)
    websocket_api.async_register_command(hass, websocket_search_media)
    hass.http.register_view(MediaPlayerImageView(component))

    await component.async_setup(config)

    async_setup_services(hass)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up a config entry."""
    if not await hass.data[DATA_COMPONENT].async_setup_entry(entry):
        raise ConfigEntryError(
            translation_domain=HOMEASSISTANT_DOMAIN,
            translation_key="platform_setup_failed",
            translation_placeholders={"platform": entry.domain, "domain": DOMAIN},
        )


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unload a config entry."""
    await hass.data[DATA_COMPONENT].async_unload_entry(entry)


class MediaPlayerImageView(HomeAssistantView):
    """Media player view to serve an image."""

    requires_auth = False
    url = "/api/media_player_proxy/{entity_id}"
    name = "api:media_player:image"
    extra_urls = [
        # Need to modify the default regex for media_content_id as it may
        # include arbitrary characters including '/','{', or '}'
        url + "/browse_media/{media_content_type}/{media_content_id:.+}",
    ]

    def __init__(self, component: EntityComponent[MediaPlayerEntity]) -> None:
        """Initialize a media player view."""
        self.component = component

    async def get(
        self,
        request: web.Request,
        entity_id: str,
        media_content_type: MediaType | str | None = None,
        media_content_id: str | None = None,
    ) -> web.Response:
        """Start a get request."""
        if (player := self.component.get_entity(entity_id)) is None:
            raise (
                web.HTTPNotFound if request[KEY_AUTHENTICATED] else web.HTTPUnauthorized
            )

        assert isinstance(player, MediaPlayerEntity)
        authenticated = (
            request[KEY_AUTHENTICATED]
            or request.query.get("token") == player.access_token
        )

        if not authenticated:
            if hdrs.AUTHORIZATION in request.headers:
                # A failed request that carried an Authorization header is a real
                # Bearer auth attempt — return 401 and let the ban middleware count
                # it as a wrong login.
                raise web.HTTPUnauthorized
            # No Authorization header: most likely a benign signed-URL / query-
            # token request whose token has expired (e.g. a browser tab left
            # open that re-fetches resources later). Return 403 so it doesn't
            # register as a wrong login and ban the user's own IP.
            raise web.HTTPForbidden

        if media_content_type and media_content_id:
            media_image_id = request.query.get("media_image_id")
            data, content_type = await player.async_get_browse_image(
                media_content_type, media_content_id, media_image_id
            )
        else:
            data, content_type = await player.async_get_media_image()

        if data is None:
            return web.Response(status=HTTPStatus.NOT_FOUND)

        headers: LooseHeaders = {CACHE_CONTROL: "max-age=3600"}
        return web.Response(body=data, content_type=content_type, headers=headers)


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "media_player/browse_media",
        probatio.Required("entity_id"): cv.entity_id,
        probatio.Inclusive(
            ATTR_MEDIA_CONTENT_TYPE,
            "media_ids",
            "media_content_type and media_content_id must be provided together",
        ): str,
        probatio.Inclusive(
            ATTR_MEDIA_CONTENT_ID,
            "media_ids",
            "media_content_type and media_content_id must be provided together",
        ): str,
    }
)
@websocket_api.async_response
async def websocket_browse_media(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Browse media available to the media_player entity.

    To use, media_player integrations can implement
    MediaPlayerEntity.async_browse_media()
    """
    player = hass.data[DATA_COMPONENT].get_entity(msg["entity_id"])

    if player is None:
        connection.send_error(msg["id"], "entity_not_found", "Entity not found")
        return

    if MediaPlayerEntityFeature.BROWSE_MEDIA not in player.supported_features:
        connection.send_message(
            websocket_api.error_message(
                msg["id"], ERR_NOT_SUPPORTED, "Player does not support browsing media"
            )
        )
        return

    media_content_type = msg.get(ATTR_MEDIA_CONTENT_TYPE)
    media_content_id = msg.get(ATTR_MEDIA_CONTENT_ID)

    try:
        payload = await player.async_browse_media(media_content_type, media_content_id)
    except NotImplementedError:
        assert player.platform
        _LOGGER.error(
            "%s allows media browsing but its integration (%s) does not",
            player.entity_id,
            player.platform.platform_name,
        )
        connection.send_message(
            websocket_api.error_message(
                msg["id"],
                ERR_NOT_SUPPORTED,
                "Integration does not support browsing media",
            )
        )
        return
    except BrowseError as err:
        connection.send_message(
            websocket_api.error_message(msg["id"], ERR_UNKNOWN_ERROR, str(err))
        )
        return

    # For backwards compat
    if isinstance(payload, BrowseMedia):
        result = payload.as_dict()
    else:
        result = payload  # type: ignore[unreachable]
        _LOGGER.warning("Browse Media should use new BrowseMedia class")

    connection.send_result(msg["id"], result)


@websocket_api.websocket_command(
    {
        probatio.Required("type"): "media_player/search_media",
        probatio.Required("entity_id"): cv.entity_id,
        probatio.Inclusive(
            ATTR_MEDIA_CONTENT_TYPE,
            "media_ids",
            "media_content_type and media_content_id must be provided together",
        ): str,
        probatio.Inclusive(
            ATTR_MEDIA_CONTENT_ID,
            "media_ids",
            "media_content_type and media_content_id must be provided together",
        ): str,
        probatio.Required(ATTR_MEDIA_SEARCH_QUERY): str,
        probatio.Optional(ATTR_MEDIA_FILTER_CLASSES): probatio.All(
            probatio.EnsureList(),
            [probatio.In([m.value for m in MediaClass])],
            lambda x: {MediaClass(item) for item in x},
        ),
    }
)
@websocket_api.async_response
async def websocket_search_media(
    hass: HomeAssistant,
    connection: websocket_api.connection.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Search media available to the media_player entity.

    To use, media_player integrations can implement
    MediaPlayerEntity.async_search_media()
    """
    player = hass.data[DATA_COMPONENT].get_entity(msg["entity_id"])

    if player is None:
        connection.send_error(msg["id"], "entity_not_found", "Entity not found")
        return

    if MediaPlayerEntityFeature.SEARCH_MEDIA not in player.supported_features:
        connection.send_message(
            websocket_api.error_message(
                msg["id"], ERR_NOT_SUPPORTED, "Player does not support searching media"
            )
        )
        return

    media_content_type = msg.get(ATTR_MEDIA_CONTENT_TYPE)
    media_content_id = msg.get(ATTR_MEDIA_CONTENT_ID)
    query = str(msg.get(ATTR_MEDIA_SEARCH_QUERY))
    media_filter_classes = msg.get(ATTR_MEDIA_FILTER_CLASSES, [])

    player.async_set_context(connection.context(msg))
    try:
        payload = await player.async_internal_search_media(
            query,
            media_content_type,
            media_content_id,
            media_filter_classes,
        )
    except SearchError as err:
        connection.send_message(
            websocket_api.error_message(msg["id"], ERR_UNKNOWN_ERROR, str(err))
        )
        return

    result = payload.as_dict()
    connection.send_result(msg["id"], result)

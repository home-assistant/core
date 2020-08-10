"""Websocket API handler for Plex integration."""
import voluptuous as vol

from homeassistant.components import websocket_api

from .const import DOMAIN as PLEX_DOMAIN, SERVERS

EXPANDABLES = ["album", "artist", "playlist", "season", "show"]


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "plex/browse_media",
        vol.Optional("server_id"): int,
        vol.Optional("library_id"): int,
        vol.Optional("media_content_id"): int,
    }
)
async def websocket_browse_media(hass, connection, msg):
    """Browse available media on the Plex server(s)."""
    payload = dict(msg)
    payload.pop("id")
    payload.pop("type")

    library_id = str(payload.get("library_id", ""))
    media_content_id = payload.get("media_content_id")

    plex_server = _lookup_plex_server(hass, connection, payload)

    if media_content_id:
        payload = {
            "media_type": "plex",
            "plex_key": media_content_id,
        }
        response = await hass.async_add_executor_job(
            _build_item_response, plex_server, payload
        )
        connection.send_result(msg["id"], response)
        return

    def libraries_info():
        """Wrap Plex library queries. Some attributes perform I/O."""
        response = []
        for library in plex_server.library.sections():
            response.append(
                {
                    "title": library.title,
                    "id": library.key,
                    "type": "library",
                    "items": library.totalSize,
                    "can_play": False,
                    "can_expand": True,
                }
            )
        return response

    def library_contents_info():
        """Wrap Plex library queries. Some attributes perform I/O."""
        response = []
        for item in library.all():
            response.append(
                {
                    "title": item.title,
                    "media_content_id": item.ratingKey,
                    "media_content_type": "plex",
                    "type": item.type,
                    "can_play": True,
                    "can_expand": True,
                }
            )
        return response

    if library_id:
        library = plex_server.library.sectionByID(library_id)
    else:
        libraries_info = await hass.async_add_executor_job(libraries_info)
        connection.send_result(msg["id"], libraries_info)
        return

    library_contents_info = await hass.async_add_executor_job(library_contents_info)
    connection.send_result(msg["id"], library_contents_info)


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "plex/lookup_media",
        vol.Required("media_type"): str,
        # Media ID lookup
        vol.Optional("media_content_id"): int,
        # Playlist field
        vol.Optional("playlist_name"): str,
        # Required for all searches below
        vol.Optional("library_name"): str,
        # Music fields
        vol.Optional("artist_name"): str,
        vol.Optional("album_name"): str,
        vol.Optional("track_name"): str,
        vol.Optional("track_number"): int,
        vol.Optional("track_name"): str,
        # TV fields
        vol.Optional("show_name"): str,
        vol.Optional("season_number"): int,
        vol.Optional("episode_number"): int,
        # Movie/video field
        vol.Optional("video_name"): str,
    }
)
async def websocket_lookup_media(hass, connection, msg):
    """Lookup and return a media search."""
    payload = dict(msg)
    payload.pop("id")
    payload.pop("type")
    if "media_content_id" in payload:
        payload["plex_key"] = payload.pop("media_content_id")

    plex_server = _lookup_plex_server(hass, connection, msg)

    media_info = await hass.async_add_executor_job(
        _build_item_response, plex_server, payload
    )

    if media_info:
        connection.send_result(msg["id"], media_info)
    else:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_FOUND, "No results"
        )


def _lookup_plex_server(hass, connection, msg):
    """Return a valid Plex server or send websocket response."""
    server_id = msg.get("server_id")

    plex_servers = list(hass.data[PLEX_DOMAIN][SERVERS].values())
    if len(plex_servers) == 1:
        return plex_servers[0]
    elif server_id is None:
        response = []
        for server in plex_servers:
            response.append(
                {
                    "title": server.name,
                    "id": server.machineIdentifier,
                    "type": "server",
                    "can_play": False,
                    "can_expand": True,
                }
            )
        connection.send_result(msg["id"], response)
        return None
    else:
        try:
            plex_server = next(
                x for x in plex_servers if x.machineIdentifier == server_id
            )
        except StopIteration:
            connection.send_error(
                msg["id"],
                websocket_api.const.ERR_NOT_FOUND,
                f"Plex server with ID {server_id} not found",
            )
            return None
        else:
            return plex_server


def _build_item_response(plex_server, payload):
    """Build the response payload for the provided media query."""
    media = plex_server.lookup_media(**payload)

    if media is None:
        return None

    media_info = {
        "title": media.title,
        "media_content_id": media.ratingKey,
        "media_content_type": "plex",
        "type": media.type,
        "can_play": True,
    }
    if media.type in EXPANDABLES:
        media_info["can_expand"] = True
        child_items = []
        for item in media:
            child_info = {
                "title": item.title,
                "media_content_id": item.ratingKey,
                "media_content_type": "plex",
                "type": item.type,
                "can_play": True,
            }
            if item.type in EXPANDABLES:
                child_info["can_expand"] = True
            child_items.append(child_info)
        media_info["contains"] = child_items
    return media_info

"""Websocket API handler for Plex integration."""
import voluptuous as vol

from homeassistant.components import websocket_api

from .const import DOMAIN as PLEX_DOMAIN, SERVERS


@websocket_api.async_response
@websocket_api.websocket_command(
    {
        vol.Required("type"): "plex/lookup_media",
        vol.Required("media_type"): str,
        vol.Required("library_name"): str,
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
        # Playlist field
        vol.Optional("playlist_name"): str,
    }
)
async def websocket_lookup_media(hass, connection, msg):
    """Lookup and return a media search."""
    plex_server = list(hass.data[PLEX_DOMAIN][SERVERS].values())[0]

    payload = dict(msg)
    payload.pop("id")
    payload.pop("type")
    media_type = payload.pop("media_type").lower()

    def lookup_media():
        """Wrap lookup call with kwarg payload."""
        return plex_server.lookup_media(media_type, **payload)

    media = await hass.async_add_executor_job(lookup_media)

    if media:
        media_info = {
            "title": media.title,
            "id": media.ratingKey,
            "type": media.type,
        }
        connection.send_result(msg["id"], media_info)
    else:
        connection.send_error(
            msg["id"], websocket_api.const.ERR_NOT_FOUND, "No results"
        )

"""Tests for Plex media browser."""
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
)
from homeassistant.components.plex.const import CONF_SERVER_IDENTIFIER, DOMAIN
from homeassistant.components.websocket_api.const import ERR_UNKNOWN_ERROR, TYPE_RESULT

from .const import DEFAULT_DATA, DEFAULT_OPTIONS
from .helpers import trigger_plex_update
from .mock_classes import MockPlexAccount, MockPlexServer

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_browse_media(hass, hass_ws_client):
    """Test getting Plex clients from plex.tv."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=DEFAULT_DATA,
        options=DEFAULT_OPTIONS,
        unique_id=DEFAULT_DATA["server_id"],
    )

    mock_plex_server = MockPlexServer(config_entry=entry)
    mock_plex_account = MockPlexAccount()

    with patch("plexapi.server.PlexServer", return_value=mock_plex_server), patch(
        "plexapi.myplex.MyPlexAccount", return_value=mock_plex_account
    ), patch(
        "homeassistant.components.plex.PlexWebsocket", autospec=True
    ) as mock_websocket:
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    websocket_client = await hass_ws_client(hass)

    trigger_plex_update(mock_websocket)
    await hass.async_block_till_done()

    media_players = hass.states.async_entity_ids("media_player")
    msg_id = 1

    # Browse base of non-existent Plex server
    await websocket_client.send_json(
        {
            "id": msg_id,
            "type": "media_player/browse_media",
            "entity_id": media_players[0],
            ATTR_MEDIA_CONTENT_TYPE: "server",
            ATTR_MEDIA_CONTENT_ID: "this server does not exist",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == msg_id
    assert msg["type"] == TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_UNKNOWN_ERROR

    # Browse base of Plex server
    msg_id += 1
    await websocket_client.send_json(
        {
            "id": msg_id,
            "type": "media_player/browse_media",
            "entity_id": media_players[0],
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == msg_id
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    result = msg["result"]
    assert result[ATTR_MEDIA_CONTENT_TYPE] == "server"
    assert result[ATTR_MEDIA_CONTENT_ID] == DEFAULT_DATA[CONF_SERVER_IDENTIFIER]
    assert len(result["children"]) == len(mock_plex_server.library.sections())

    tvshows = next(iter(x for x in result["children"] if x["title"] == "TV Shows"))
    playlists = next(iter(x for x in result["children"] if x["title"] == "Playlists"))

    # Browse into a Plex TV show library
    msg_id += 1
    await websocket_client.send_json(
        {
            "id": msg_id,
            "type": "media_player/browse_media",
            "entity_id": media_players[0],
            ATTR_MEDIA_CONTENT_TYPE: tvshows[ATTR_MEDIA_CONTENT_TYPE],
            ATTR_MEDIA_CONTENT_ID: str(tvshows[ATTR_MEDIA_CONTENT_ID]),
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == msg_id
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    result = msg["result"]
    assert result[ATTR_MEDIA_CONTENT_TYPE] == "library"
    result_id = result[ATTR_MEDIA_CONTENT_ID]
    assert len(result["children"]) == len(
        mock_plex_server.library.sectionByID(result_id).all()
    )

    # Browse into a Plex TV show
    msg_id += 1
    await websocket_client.send_json(
        {
            "id": msg_id,
            "type": "media_player/browse_media",
            "entity_id": media_players[0],
            ATTR_MEDIA_CONTENT_TYPE: result["children"][0][ATTR_MEDIA_CONTENT_TYPE],
            ATTR_MEDIA_CONTENT_ID: str(result["children"][0][ATTR_MEDIA_CONTENT_ID]),
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == msg_id
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    result = msg["result"]
    assert result[ATTR_MEDIA_CONTENT_TYPE] == "show"
    result_id = int(result[ATTR_MEDIA_CONTENT_ID])
    assert result["title"] == mock_plex_server.fetchItem(result_id).title

    # Browse into a non-existent TV season
    msg_id += 1
    await websocket_client.send_json(
        {
            "id": msg_id,
            "type": "media_player/browse_media",
            "entity_id": media_players[0],
            ATTR_MEDIA_CONTENT_TYPE: result["children"][0][ATTR_MEDIA_CONTENT_TYPE],
            ATTR_MEDIA_CONTENT_ID: str(99999999999999),
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == msg_id
    assert msg["type"] == TYPE_RESULT
    assert not msg["success"]
    assert msg["error"]["code"] == ERR_UNKNOWN_ERROR

    # Browse Plex playlists
    msg_id += 1
    await websocket_client.send_json(
        {
            "id": msg_id,
            "type": "media_player/browse_media",
            "entity_id": media_players[0],
            ATTR_MEDIA_CONTENT_TYPE: playlists[ATTR_MEDIA_CONTENT_TYPE],
            ATTR_MEDIA_CONTENT_ID: str(playlists[ATTR_MEDIA_CONTENT_ID]),
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == msg_id
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    result = msg["result"]
    assert result[ATTR_MEDIA_CONTENT_TYPE] == "playlists"
    result_id = result[ATTR_MEDIA_CONTENT_ID]

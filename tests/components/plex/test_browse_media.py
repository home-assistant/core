"""Tests for Plex media browser."""
from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
)
from homeassistant.components.plex.const import CONF_SERVER_IDENTIFIER
from homeassistant.components.plex.media_browser import SPECIAL_METHODS
from homeassistant.components.websocket_api.const import ERR_UNKNOWN_ERROR, TYPE_RESULT

from .const import DEFAULT_DATA
from .helpers import trigger_plex_update


async def test_browse_media(hass, hass_ws_client, mock_plex_server, mock_websocket):
    """Test getting Plex clients from plex.tv."""
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
    assert len(result["children"]) == len(mock_plex_server.library.sections()) + len(
        SPECIAL_METHODS
    )

    tvshows = next(iter(x for x in result["children"] if x["title"] == "TV Shows"))
    playlists = next(iter(x for x in result["children"] if x["title"] == "Playlists"))
    special_keys = list(SPECIAL_METHODS.keys())

    # Browse into a special folder (server)
    msg_id += 1
    await websocket_client.send_json(
        {
            "id": msg_id,
            "type": "media_player/browse_media",
            "entity_id": media_players[0],
            ATTR_MEDIA_CONTENT_TYPE: "server",
            ATTR_MEDIA_CONTENT_ID: f"{DEFAULT_DATA[CONF_SERVER_IDENTIFIER]}:{special_keys[0]}",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == msg_id
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    result = msg["result"]
    assert result[ATTR_MEDIA_CONTENT_TYPE] == "server"
    assert (
        result[ATTR_MEDIA_CONTENT_ID]
        == f"{DEFAULT_DATA[CONF_SERVER_IDENTIFIER]}:{special_keys[0]}"
    )
    assert len(result["children"]) == len(mock_plex_server.library.onDeck())

    # Browse into a special folder (library)
    msg_id += 1
    library_section_id = next(iter(mock_plex_server.library.sections())).key
    await websocket_client.send_json(
        {
            "id": msg_id,
            "type": "media_player/browse_media",
            "entity_id": media_players[0],
            ATTR_MEDIA_CONTENT_TYPE: "library",
            ATTR_MEDIA_CONTENT_ID: f"{library_section_id}:{special_keys[1]}",
        }
    )

    msg = await websocket_client.receive_json()
    assert msg["id"] == msg_id
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    result = msg["result"]
    assert result[ATTR_MEDIA_CONTENT_TYPE] == "library"
    assert result[ATTR_MEDIA_CONTENT_ID] == f"{library_section_id}:{special_keys[1]}"
    assert len(result["children"]) == len(
        mock_plex_server.library.sectionByID(library_section_id).recentlyAdded()
    )

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
    ) + len(SPECIAL_METHODS)

    # Browse into a Plex TV show
    msg_id += 1
    await websocket_client.send_json(
        {
            "id": msg_id,
            "type": "media_player/browse_media",
            "entity_id": media_players[0],
            ATTR_MEDIA_CONTENT_TYPE: result["children"][-1][ATTR_MEDIA_CONTENT_TYPE],
            ATTR_MEDIA_CONTENT_ID: str(result["children"][-1][ATTR_MEDIA_CONTENT_ID]),
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

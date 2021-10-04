"""Tests for Plex media browser."""
from unittest.mock import patch

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
)
from homeassistant.components.plex.const import CONF_SERVER_IDENTIFIER
from homeassistant.components.websocket_api.const import ERR_UNKNOWN_ERROR, TYPE_RESULT

from .const import DEFAULT_DATA


class MockPlexShow:
    """Mock a plexapi Season instance."""

    ratingKey = 30
    title = "TV Show"
    type = "show"

    def __iter__(self):
        """Iterate over episodes."""
        yield MockPlexSeason()


class MockPlexSeason:
    """Mock a plexapi Season instance."""

    ratingKey = 20
    title = "Season 1"
    type = "season"
    year = 2021

    def __iter__(self):
        """Iterate over episodes."""
        yield MockPlexEpisode()


class MockPlexEpisode:
    """Mock a plexapi Episode instance."""

    ratingKey = 10
    title = "Episode 1"
    grandparentTitle = "TV Show"
    seasonEpisode = "s01e01"
    type = "episode"


class MockPlexArtist:
    """Mock a plexapi Artist instance."""

    ratingKey = 300
    title = "Artist"
    type = "artist"

    def __iter__(self):
        """Iterate over albums."""
        yield MockPlexAlbum()


class MockPlexAlbum:
    """Mock a plexapi Album instance."""

    ratingKey = 200
    parentTitle = "Artist"
    title = "Album"
    type = "album"
    year = 2019

    def __iter__(self):
        """Iterate over tracks."""
        yield MockPlexTrack()


class MockPlexTrack:
    """Mock a plexapi Track instance."""

    index = 1
    ratingKey = 100
    title = "Track 1"
    type = "track"


async def test_browse_media(
    hass,
    hass_ws_client,
    mock_plex_server,
    requests_mock,
    library_movies_filtertypes,
    empty_payload,
):
    """Test getting Plex clients from plex.tv."""
    websocket_client = await hass_ws_client(hass)

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
    # Library Sections + On Deck + Recently Added + Playlists
    assert len(result["children"]) == len(mock_plex_server.library.sections()) + 3

    music = next(iter(x for x in result["children"] if x["title"] == "Music"))
    tvshows = next(iter(x for x in result["children"] if x["title"] == "TV Shows"))
    playlists = next(iter(x for x in result["children"] if x["title"] == "Playlists"))
    special_keys = ["On Deck", "Recently Added"]

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
    requests_mock.get(
        f"{mock_plex_server.url_in_use}/library/sections/1/all?includeMeta=1",
        text=library_movies_filtertypes,
    )
    requests_mock.get(
        f"{mock_plex_server.url_in_use}/library/sections/1/collections?includeMeta=1",
        text=empty_payload,
    )

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
    result_id = int(result[ATTR_MEDIA_CONTENT_ID])
    # All items in section + On Deck + Recently Added
    assert (
        len(result["children"])
        == len(mock_plex_server.library.sectionByID(result_id).all()) + 2
    )

    # Browse into a Plex TV show
    msg_id += 1
    mock_show = MockPlexShow()
    mock_season = next(iter(mock_show))
    with patch.object(
        mock_plex_server, "fetch_item", return_value=mock_show
    ) as mock_fetch:
        await websocket_client.send_json(
            {
                "id": msg_id,
                "type": "media_player/browse_media",
                "entity_id": media_players[0],
                ATTR_MEDIA_CONTENT_TYPE: result["children"][-1][
                    ATTR_MEDIA_CONTENT_TYPE
                ],
                ATTR_MEDIA_CONTENT_ID: str(
                    result["children"][-1][ATTR_MEDIA_CONTENT_ID]
                ),
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["id"] == msg_id
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    result = msg["result"]
    assert result[ATTR_MEDIA_CONTENT_TYPE] == "show"
    result_id = int(result[ATTR_MEDIA_CONTENT_ID])
    assert result["title"] == mock_plex_server.fetch_item(result_id).title
    assert result["children"][0]["title"] == f"{mock_season.title} ({mock_season.year})"

    # Browse into a Plex TV show season
    msg_id += 1
    mock_episode = next(iter(mock_season))
    with patch.object(
        mock_plex_server, "fetch_item", return_value=mock_season
    ) as mock_fetch:
        await websocket_client.send_json(
            {
                "id": msg_id,
                "type": "media_player/browse_media",
                "entity_id": media_players[0],
                ATTR_MEDIA_CONTENT_TYPE: result["children"][0][ATTR_MEDIA_CONTENT_TYPE],
                ATTR_MEDIA_CONTENT_ID: str(
                    result["children"][0][ATTR_MEDIA_CONTENT_ID]
                ),
            }
        )

        msg = await websocket_client.receive_json()

    assert mock_fetch.called
    assert msg["id"] == msg_id
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    result = msg["result"]
    assert result[ATTR_MEDIA_CONTENT_TYPE] == "season"
    result_id = int(result[ATTR_MEDIA_CONTENT_ID])
    assert result["title"] == f"{mock_season.title} ({mock_season.year})"
    assert (
        result["children"][0]["title"]
        == f"{mock_episode.seasonEpisode.upper()} - {mock_episode.title}"
    )

    # Browse into a Plex music library
    msg_id += 1
    await websocket_client.send_json(
        {
            "id": msg_id,
            "type": "media_player/browse_media",
            "entity_id": media_players[0],
            ATTR_MEDIA_CONTENT_TYPE: music[ATTR_MEDIA_CONTENT_TYPE],
            ATTR_MEDIA_CONTENT_ID: str(music[ATTR_MEDIA_CONTENT_ID]),
        }
    )
    msg = await websocket_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    result_id = int(result[ATTR_MEDIA_CONTENT_ID])
    assert result[ATTR_MEDIA_CONTENT_TYPE] == "library"
    assert result["title"] == "Music"

    # Browse into a Plex artist
    msg_id += 1
    mock_artist = MockPlexArtist()
    mock_album = next(iter(MockPlexArtist()))
    mock_track = next(iter(MockPlexAlbum()))
    with patch.object(
        mock_plex_server, "fetch_item", return_value=mock_artist
    ) as mock_fetch:
        await websocket_client.send_json(
            {
                "id": msg_id,
                "type": "media_player/browse_media",
                "entity_id": media_players[0],
                ATTR_MEDIA_CONTENT_TYPE: result["children"][-1][
                    ATTR_MEDIA_CONTENT_TYPE
                ],
                ATTR_MEDIA_CONTENT_ID: str(
                    result["children"][-1][ATTR_MEDIA_CONTENT_ID]
                ),
            }
        )
        msg = await websocket_client.receive_json()

    assert mock_fetch.called
    assert msg["success"]
    result = msg["result"]
    result_id = int(result[ATTR_MEDIA_CONTENT_ID])
    assert result[ATTR_MEDIA_CONTENT_TYPE] == "artist"
    assert result["title"] == mock_artist.title
    assert result["children"][0]["title"] == f"{mock_album.title} ({mock_album.year})"

    # Browse into a Plex album
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

    assert msg["success"]
    result = msg["result"]
    result_id = int(result[ATTR_MEDIA_CONTENT_ID])
    assert result[ATTR_MEDIA_CONTENT_TYPE] == "album"
    assert (
        result["title"]
        == f"{mock_artist.title} - {mock_album.title} ({mock_album.year})"
    )
    assert result["children"][0]["title"] == f"{mock_track.index}. {mock_track.title}"

    # Browse into a non-existent TV season
    unknown_key = 99999999999999
    requests_mock.get(
        f"{mock_plex_server.url_in_use}/library/metadata/{unknown_key}", status_code=404
    )

    msg_id += 1
    await websocket_client.send_json(
        {
            "id": msg_id,
            "type": "media_player/browse_media",
            "entity_id": media_players[0],
            ATTR_MEDIA_CONTENT_TYPE: result["children"][0][ATTR_MEDIA_CONTENT_TYPE],
            ATTR_MEDIA_CONTENT_ID: str(unknown_key),
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

    # Browse recently added items
    msg_id += 1
    mock_items = [MockPlexAlbum(), MockPlexEpisode(), MockPlexSeason(), MockPlexTrack()]
    with patch("plexapi.library.Library.search", return_value=mock_items) as mock_fetch:
        await websocket_client.send_json(
            {
                "id": msg_id,
                "type": "media_player/browse_media",
                "entity_id": media_players[0],
                ATTR_MEDIA_CONTENT_TYPE: "server",
                ATTR_MEDIA_CONTENT_ID: f"{DEFAULT_DATA[CONF_SERVER_IDENTIFIER]}:{special_keys[1]}",
            }
        )
        msg = await websocket_client.receive_json()

    assert msg["success"]
    result = msg["result"]
    assert result[ATTR_MEDIA_CONTENT_TYPE] == "server"
    result_id = result[ATTR_MEDIA_CONTENT_ID]
    for child in result["children"]:
        assert child["media_content_type"] in ["album", "episode"]
        assert child["media_content_type"] not in ["season", "track"]

"""Media browsing tests for the forked_daapd media player platform."""

from http import HTTPStatus
from unittest.mock import patch

from homeassistant.components import media_source, spotify
from homeassistant.components.forked_daapd.browse_media import (
    MediaContent,
    create_media_content_id,
    is_owntone_media_content_id,
)
from homeassistant.components.media_player import BrowseMedia, MediaClass, MediaType
from homeassistant.components.spotify.const import (  # pylint: disable=hass-component-root-import
    MEDIA_PLAYER_PREFIX as SPOTIFY_MEDIA_PLAYER_PREFIX,
)
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator, WebSocketGenerator

TEST_MASTER_ENTITY_NAME = "media_player.owntone_server"


async def test_async_browse_media(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test browse media."""

    assert await async_setup_component(hass, media_source.DOMAIN, {})
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.forked_daapd.ForkedDaapdAPI",
        autospec=True,
    ) as mock_api:
        mock_api.return_value.get_request.return_value = {"websocket_port": 2}
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        mock_api.return_value.full_url = lambda x: "http://owntone_instance/" + x
        mock_api.return_value.get_directory.side_effect = [
            {
                "directories": [
                    {"path": "/music/srv/Audiobooks"},
                    {"path": "/music/srv/Music"},
                    {"path": "/music/srv/Playlists"},
                    {"path": "/music/srv/Podcasts"},
                ],
                "tracks": {
                    "items": [
                        {
                            "id": 1,
                            "title": "input.pipe",
                            "artist": "Unknown artist",
                            "artist_sort": "Unknown artist",
                            "album": "Unknown album",
                            "album_sort": "Unknown album",
                            "album_id": "4201163758598356043",
                            "album_artist": "Unknown artist",
                            "album_artist_sort": "Unknown artist",
                            "album_artist_id": "4187901437947843388",
                            "genre": "Unknown genre",
                            "year": 0,
                            "track_number": 0,
                            "disc_number": 0,
                            "length_ms": 0,
                            "play_count": 0,
                            "skip_count": 0,
                            "time_added": "2018-11-24T08:41:35Z",
                            "seek_ms": 0,
                            "media_kind": "music",
                            "data_kind": "pipe",
                            "path": "/music/srv/input.pipe",
                            "uri": "library:track:1",
                            "artwork_url": "/artwork/item/1",
                        }
                    ],
                    "total": 1,
                    "offset": 0,
                    "limit": -1,
                },
                "playlists": {
                    "items": [
                        {
                            "id": 8,
                            "name": "radio",
                            "path": "/music/srv/radio.m3u",
                            "smart_playlist": True,
                            "uri": "library:playlist:8",
                        }
                    ],
                    "total": 1,
                    "offset": 0,
                    "limit": -1,
                },
            }
        ] + 4 * [
            {"directories": [], "tracks": {"items": []}, "playlists": {"items": []}}
        ]
        mock_api.return_value.get_albums.return_value = [
            {
                "id": "8009851123233197743",
                "name": "Add Violence",
                "name_sort": "Add Violence",
                "artist": "Nine Inch Nails",
                "artist_id": "32561671101664759",
                "track_count": 5,
                "length_ms": 1634961,
                "uri": "library:album:8009851123233197743",
            },
        ]
        mock_api.return_value.get_artists.return_value = [
            {
                "id": "3815427709949443149",
                "name": "ABAY",
                "name_sort": "ABAY",
                "album_count": 1,
                "track_count": 10,
                "length_ms": 2951554,
                "uri": "library:artist:3815427709949443149",
            },
            {
                "id": "456",
                "name": "Spotify Artist",
                "name_sort": "Spotify Artist",
                "album_count": 1,
                "track_count": 10,
                "length_ms": 2254,
                "uri": "spotify:artist:abc123",
                "data_kind": "spotify",
            },
        ]
        mock_api.return_value.get_genres.return_value = [
            {"name": "Classical"},
            {"name": "Drum & Bass"},
            {"name": "Pop"},
            {"name": "Rock/Pop"},
            {"name": "'90s Alternative"},
        ]
        mock_api.return_value.get_playlists.return_value = [
            {
                "id": 1,
                "name": "radio",
                "path": "/music/srv/radio.m3u",
                "smart_playlist": False,
                "uri": "library:playlist:1",
            },
            {
                "id": 2,
                "name": "Spotify Playlist",
                "path": "spotify:playlist:abc123",
                "smart_playlist": False,
                "uri": "library:playlist:2",
            },
        ]

        # Request browse root through WebSocket
        client = await hass_ws_client(hass)
        await client.send_json(
            {
                "id": 1,
                "type": "media_player/browse_media",
                "entity_id": TEST_MASTER_ENTITY_NAME,
            }
        )
        msg = await client.receive_json()
        # Assert WebSocket response
        assert msg["id"] == 1
        assert msg["type"] == TYPE_RESULT
        assert msg["success"]

        msg_id = 2

        async def browse_children(children):
            """Browse the children of this BrowseMedia."""
            nonlocal msg_id
            for child in children:
                # Assert Spotify content is not passed through as OwnTone media
                assert not (
                    is_owntone_media_content_id(child["media_content_id"])
                    and "Spotify" in MediaContent(child["media_content_id"]).title
                )
                if child["can_expand"]:
                    await client.send_json(
                        {
                            "id": msg_id,
                            "type": "media_player/browse_media",
                            "entity_id": TEST_MASTER_ENTITY_NAME,
                            "media_content_type": child["media_content_type"],
                            "media_content_id": child["media_content_id"],
                        }
                    )
                    msg = await client.receive_json()
                    assert msg["success"]
                    msg_id += 1
                    await browse_children(msg["result"]["children"])

        await browse_children(msg["result"]["children"])


async def test_async_browse_media_not_found(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test browse media not found."""

    assert await async_setup_component(hass, media_source.DOMAIN, {})
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.forked_daapd.ForkedDaapdAPI",
        autospec=True,
    ) as mock_api:
        mock_api.return_value.get_request.return_value = {"websocket_port": 2}
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        mock_api.return_value.get_directory.return_value = None
        mock_api.return_value.get_albums.return_value = None
        mock_api.return_value.get_artists.return_value = None
        mock_api.return_value.get_genres.return_value = None
        mock_api.return_value.get_playlists.return_value = None

        # Request different types of media through WebSocket
        client = await hass_ws_client(hass)
        msg_id = 1
        for media_type in (
            "directory",
            MediaType.ALBUM,
            MediaType.ARTIST,
            MediaType.GENRE,
            MediaType.PLAYLIST,
        ):
            await client.send_json(
                {
                    "id": msg_id,
                    "type": "media_player/browse_media",
                    "entity_id": TEST_MASTER_ENTITY_NAME,
                    "media_content_type": media_type,
                    "media_content_id": (
                        media_content_id := create_media_content_id(
                            "title", f"library:{media_type}:"
                        )
                    ),
                }
            )
            msg = await client.receive_json()
            # Assert WebSocket response
            assert msg["id"] == msg_id
            assert msg["type"] == TYPE_RESULT
            assert not msg["success"]
            assert (
                msg["error"]["message"]
                == f"Media not found for {media_type} / {media_content_id}"
            )
            msg_id += 1


async def test_async_browse_spotify(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test browsing spotify."""

    assert await async_setup_component(hass, spotify.DOMAIN, {})
    await hass.async_block_till_done()
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.forked_daapd.media_player.spotify_async_browse_media"
    ) as mock_spotify_browse:
        children = [
            BrowseMedia(
                title="Spotify",
                media_class=MediaClass.APP,
                media_content_id=f"{SPOTIFY_MEDIA_PLAYER_PREFIX}some_id",
                media_content_type=f"{SPOTIFY_MEDIA_PLAYER_PREFIX}track",
                thumbnail="https://brands.home-assistant.io/_/spotify/logo.png",
                can_play=False,
                can_expand=True,
            )
        ]
        mock_spotify_browse.return_value = BrowseMedia(
            title="Spotify",
            media_class=MediaClass.APP,
            media_content_id=SPOTIFY_MEDIA_PLAYER_PREFIX,
            media_content_type=f"{SPOTIFY_MEDIA_PLAYER_PREFIX}library",
            thumbnail="https://brands.home-assistant.io/_/spotify/logo.png",
            can_play=False,
            can_expand=True,
            children=children,
        )

        client = await hass_ws_client(hass)
        await client.send_json(
            {
                "id": 1,
                "type": "media_player/browse_media",
                "entity_id": TEST_MASTER_ENTITY_NAME,
                "media_content_type": f"{SPOTIFY_MEDIA_PLAYER_PREFIX}library",
                "media_content_id": SPOTIFY_MEDIA_PLAYER_PREFIX,
            }
        )
        msg = await client.receive_json()
        # Assert WebSocket response
        assert msg["id"] == 1
        assert msg["type"] == TYPE_RESULT
        assert msg["success"]


async def test_async_browse_media_source(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test browsing media_source."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    with patch(
        "homeassistant.components.forked_daapd.media_player.media_source.async_browse_media"
    ) as mock_media_source_browse:
        children = [
            BrowseMedia(
                title="Test mp3",
                media_class=MediaClass.MUSIC,
                media_content_id="media-source://test_dir/test.mp3",
                media_content_type="audio/aac",
                can_play=False,
                can_expand=True,
            )
        ]
        mock_media_source_browse.return_value = BrowseMedia(
            title="Audio Folder",
            media_class=MediaClass.DIRECTORY,
            media_content_id="media-source://audio_folder",
            media_content_type=MediaType.APP,
            can_play=False,
            can_expand=True,
            children=children,
        )

        client = await hass_ws_client(hass)
        await client.send_json(
            {
                "id": 1,
                "type": "media_player/browse_media",
                "entity_id": TEST_MASTER_ENTITY_NAME,
                "media_content_type": MediaType.APP,
                "media_content_id": "media-source://audio_folder",
            }
        )
        msg = await client.receive_json()
        # Assert WebSocket response
        assert msg["id"] == 1
        assert msg["type"] == TYPE_RESULT
        assert msg["success"]


async def test_async_browse_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test browse media images."""

    with patch(
        "homeassistant.components.forked_daapd.ForkedDaapdAPI",
        autospec=True,
    ) as mock_api:
        mock_api.return_value.get_request.return_value = {"websocket_port": 2}
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        client = await hass_client()
        mock_api.return_value.full_url = lambda x: "http://owntone_instance/" + x
        mock_api.return_value.get_albums.return_value = [
            {"id": "8009851123233197743", "artwork_url": "some_album_image"},
        ]
        mock_api.return_value.get_artists.return_value = [
            {"id": "3815427709949443149", "artwork_url": "some_artist_image"},
        ]
        mock_api.return_value.get_track.return_value = {
            "id": 456,
            "artwork_url": "some_track_image",
        }
        media_content_id = create_media_content_id(
            "title", media_type=MediaType.ALBUM, id_or_path="8009851123233197743"
        )

        with patch(
            "homeassistant.components.media_player.async_fetch_image"
        ) as mock_fetch_image:
            for media_type, media_id in (
                (MediaType.ALBUM, "8009851123233197743"),
                (MediaType.ARTIST, "3815427709949443149"),
                (MediaType.TRACK, "456"),
            ):
                mock_fetch_image.return_value = (b"image_bytes", "image/jpeg")
                media_content_id = create_media_content_id(
                    "title", media_type=media_type, id_or_path=media_id
                )
                resp = await client.get(
                    f"/api/media_player_proxy/{TEST_MASTER_ENTITY_NAME}/browse_media/{media_type}/{media_content_id}"
                )
                assert (
                    mock_fetch_image.call_args[0][2]
                    == f"http://owntone_instance/some_{media_type}_image"
                )
                assert resp.status == HTTPStatus.OK
                assert resp.content_type == "image/jpeg"
                assert await resp.read() == b"image_bytes"


async def test_async_browse_image_missing(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
) -> None:
    """Test browse media images with no image available."""

    with patch(
        "homeassistant.components.forked_daapd.ForkedDaapdAPI",
        autospec=True,
    ) as mock_api:
        mock_api.return_value.get_request.return_value = {"websocket_port": 2}
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        client = await hass_client()
        mock_api.return_value.full_url = lambda x: "http://owntone_instance/" + x
        mock_api.return_value.get_track.return_value = {}

        media_content_id = create_media_content_id(
            "title", media_type=MediaType.TRACK, id_or_path="456"
        )
        resp = await client.get(
            f"/api/media_player_proxy/{TEST_MASTER_ENTITY_NAME}/browse_media/{MediaType.TRACK}/{media_content_id}"
        )
        assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR

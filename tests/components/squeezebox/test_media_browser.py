"""Test the media browser interface."""

<<<<<<< HEAD
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    BrowseError,
    MediaType,
)
from homeassistant.components.squeezebox.browse_media import (
    LIBRARY,
    MEDIA_TYPE_TO_SQUEEZEBOX,
)
from homeassistant.const import ATTR_ENTITY_ID
=======
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.media_player import BrowseError, BrowseMedia, MediaType
from homeassistant.components.squeezebox.browse_media import (
    LIBRARY,
    MEDIA_TYPE_TO_SQUEEZEBOX,
    SQUEEZEBOX_ID_BY_TYPE,
)
from homeassistant.components.squeezebox.const import DOMAIN, KNOWN_PLAYERS
from homeassistant.components.squeezebox.media_player import SqueezeBoxEntity
>>>>>>> 3d3e5699d7 (Improve unit tests)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, lms: MagicMock
) -> None:
    """Fixture for setting up the component."""
<<<<<<< HEAD
    with (
        patch("homeassistant.components.squeezebox.Server", return_value=lms),
        patch(
            "homeassistant.components.squeezebox.media_player.start_server_discovery"
        ),
    ):
=======
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.squeezebox.Server", return_value=lms):
>>>>>>> 3d3e5699d7 (Improve unit tests)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)


<<<<<<< HEAD
async def test_async_browse_media_root(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the async_browse_media function at the root level."""

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.test_player",
            "media_content_id": "",
            "media_content_type": "library",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    result = response["result"]
    for idx, item in enumerate(result["children"]):
        assert item["title"] == LIBRARY[idx]


async def test_async_browse_media_with_subitems(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test each category with subitems."""
    for category in ("Favorites", "Artists", "Albums", "Playlists", "Genres"):
        with patch(
            "homeassistant.components.squeezebox.browse_media.is_internal_request",
            return_value=False,
        ):
            client = await hass_ws_client()
            await client.send_json(
                {
                    "id": 1,
                    "type": "media_player/browse_media",
                    "entity_id": "media_player.test_player",
                    "media_content_id": "",
                    "media_content_type": category,
                }
            )
            response = await client.receive_json()
            assert response["success"]
            category_level = response["result"]
            assert category_level["title"] == MEDIA_TYPE_TO_SQUEEZEBOX[category]
            assert category_level["children"][0]["title"] == "Fake Item 1"

            # Look up a subitem
            search_type = category_level["children"][0]["media_content_type"]
            search_id = category_level["children"][0]["media_content_id"]
            await client.send_json(
                {
                    "id": 2,
                    "type": "media_player/browse_media",
                    "entity_id": "media_player.test_player",
                    "media_content_id": search_id,
                    "media_content_type": search_type,
                }
            )
            response = await client.receive_json()
            assert response["success"]
            search = response["result"]
            assert search["title"] == "Fake Item 1"


async def test_async_browse_tracks(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
=======
@pytest.fixture
async def player(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> SqueezeBoxEntity:
    """Mock the pysqueezebox player.async_browse function for testing."""
    player = hass.data[DOMAIN][KNOWN_PLAYERS][0]

    # Mock the player.async_browse method
    async def mock_async_browse(
        media_type: MediaType, limit: int, browse_id: tuple | None = None
    ) -> dict | None:
        child_types = {
            "favorites": "favorites",
            "albums": "album",
            "album": "track",
            "genres": "genre",
            "genre": "album",
            "artists": "artist",
            "artist": "album",
            "titles": "title",
            "title": "title",
            "playlists": "playlist",
            "playlist": "title",
        }
        fake_items = [
            {
                "title": "Fake Item 1",
                "id": "1234",
                "hasitems": False,
                "item_type": child_types[media_type],
                "artwork_track_id": "b35bb9e9",
            },
            {
                "title": "Fake Item 2",
                "id": "12345",
                "hasitems": media_type == "favorites",
                "item_type": child_types[media_type],
                "image_url": "http://lms.internal:9000/html/images/favorites.png",
            },
            {
                "title": "Fake Item 3",
                "id": "123456",
                "hasitems": media_type == "favorites",
                "album_id": "123456" if media_type == "favorites" else None,
            },
        ]

        if browse_id:
            search_type, search_id = browse_id
            if search_id:
                if search_type in SQUEEZEBOX_ID_BY_TYPE.values():
                    for item in fake_items:
                        if item["id"] == search_id:
                            return {
                                "title": item["title"],
                                "items": [item],
                            }
                return None
            if search_type in SQUEEZEBOX_ID_BY_TYPE.values():
                return {
                    "title": search_type,
                    "items": fake_items,
                }
            return None
        if media_type in MEDIA_TYPE_TO_SQUEEZEBOX.values():
            return {
                "title": media_type,
                "items": fake_items,
            }
        return None

    player._player.async_browse.side_effect = mock_async_browse
    player._player.async_load_playlist = AsyncMock()
    return player


async def test_async_browse_media_root(
    hass: HomeAssistant, config_entry: MockConfigEntry, player: SqueezeBoxEntity
) -> None:
    """Test the async_browse_media function at the root level."""

    root = await player.async_browse_media()
    assert type(root) is BrowseMedia
    for idx, item in enumerate(root.as_dict()["children"]):
        assert item["title"] == LIBRARY[idx]


async def test_async_browse_media_with_subitems(
    hass: HomeAssistant, config_entry: MockConfigEntry, player: SqueezeBoxEntity
) -> None:
    """Test each category with subitems."""
    for category in ("Favorites", "Artists", "Albums", "Playlists", "Genres"):
        with patch(
            "homeassistant.components.squeezebox.browse_media.is_internal_request",
            return_value=False,
        ):
            category_level = await player.async_browse_media(category)
            assert type(category_level) is BrowseMedia
            assert (
                category_level.as_dict()["title"] == MEDIA_TYPE_TO_SQUEEZEBOX[category]
            )
            assert category_level.as_dict()["children"][0]["title"] == "Fake Item 1"

            # Look up a subitem
            search_type = category_level.as_dict()["children"][0]["media_content_type"]
            search_id = category_level.as_dict()["children"][0]["media_content_id"]
            search = await player.async_browse_media(search_type, search_id)
            assert search.as_dict()["title"] == "Fake Item 1"


async def test_async_browse_tracks(
    hass: HomeAssistant, config_entry: MockConfigEntry, player: SqueezeBoxEntity
>>>>>>> 3d3e5699d7 (Improve unit tests)
) -> None:
    """Test tracks (no subitems)."""
    with patch(
        "homeassistant.components.squeezebox.browse_media.is_internal_request",
        return_value=True,
    ):
<<<<<<< HEAD
        client = await hass_ws_client()
        await client.send_json(
            {
                "id": 1,
                "type": "media_player/browse_media",
                "entity_id": "media_player.test_player",
                "media_content_id": "",
                "media_content_type": "Tracks",
            }
        )
        response = await client.receive_json()
        assert response["success"]
        tracks = response["result"]
        assert tracks["title"] == "titles"
        assert len(tracks["children"]) == 3


async def test_async_browse_error(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Search for a non-existent item and assert error."""
    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.test_player",
            "media_content_id": "0",
            "media_content_type": MediaType.ALBUM,
        }
    )
    response = await client.receive_json()
    assert not response["success"]


async def test_play_browse_item(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test play browse item."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_ID: "1234",
            ATTR_MEDIA_CONTENT_TYPE: "album",
        },
=======
        tracks = await player.async_browse_media("Tracks")
        assert type(tracks) is BrowseMedia
        assert tracks.as_dict()["title"] == "titles"
        assert len(tracks.as_dict()["children"]) == 3


async def test_async_browse_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, player: SqueezeBoxEntity
) -> None:
    """Search for a non-existent item and assert BrowseError is raised."""
    with pytest.raises(BrowseError):
        await player.async_browse_media(MediaType.ALBUM, "0")


async def test_play_browse_item(
    hass: HomeAssistant, config_entry: MockConfigEntry, player: SqueezeBoxEntity
) -> None:
    """Test play browse item."""
    await player.async_play_media(
        media_type=MediaType.PLAYLIST,
        media_id="1234",
>>>>>>> 3d3e5699d7 (Improve unit tests)
    )


async def test_play_browse_item_nonexistent(
<<<<<<< HEAD
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test trying to play an item that doesn't exist."""
    with pytest.raises(BrowseError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_CONTENT_ID: "0",
                ATTR_MEDIA_CONTENT_TYPE: "album",
            },
            blocking=True,
        )


async def test_play_browse_item_bad_category(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test trying to play an item whose category doesn't exist."""
    with pytest.raises(BrowseError):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.test_player",
                ATTR_MEDIA_CONTENT_ID: "1234",
                ATTR_MEDIA_CONTENT_TYPE: "bad_category",
            },
            blocking=True,
        )
=======
    hass: HomeAssistant, config_entry: MockConfigEntry, player: SqueezeBoxEntity
) -> None:
    """Test trying to play an item that doesn't exist."""
    await player.async_play_media(
        media_type=MediaType.PLAYLIST,
        media_id="1234567890",
    )


async def test_play_browse_item_bad_category(
    hass: HomeAssistant, config_entry: MockConfigEntry, player: SqueezeBoxEntity
) -> None:
    """Test trying to play an item whose category doesn't exist."""
    await player.async_play_media(
        media_type="bad_category",
        media_id="1234",
    )
>>>>>>> 3d3e5699d7 (Improve unit tests)

"""Test the media browser interface."""

from typing import Any
from unittest.mock import ANY, MagicMock, call, patch

import pytest

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    BrowseError,
    MediaClass,
    MediaType,
)
from homeassistant.components.squeezebox.browse_media import (
    LIBRARY,
    MEDIA_TYPE_TO_SQUEEZEBOX,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from .conftest import FAKE_VALID_ITEM_ID

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, lms: MagicMock
) -> None:
    """Fixture for setting up the component."""
    with (
        patch("homeassistant.components.squeezebox.Server", return_value=lms),
        patch(
            "homeassistant.components.squeezebox.PLATFORMS",
            [Platform.MEDIA_PLAYER],
        ),
        patch(
            "homeassistant.components.squeezebox.media_player.start_server_discovery"
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)


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
        assert item["title"].lower() == LIBRARY[idx]


@pytest.mark.parametrize(
    ("category", "child_count", "can_search"),
    [
        ("favorites", 4, False),
        ("artists", 4, True),
        ("albums", 4, True),
        ("playlists", 4, False),
        ("genres", 4, True),
        ("new music", 4, True),
        ("album artists", 4, True),
        ("apps", 3, False),
        ("radios", 3, False),
    ],
)
async def test_async_browse_media_with_subitems(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    category: str,
    child_count: int,
    can_search: bool,
) -> None:
    """Test each category with subitems."""
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
        assert category_level["children"][0]["can_search"] is can_search
        assert len(category_level["children"]) == child_count

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
        assert search["can_search"] is can_search


async def test_async_browse_playlist(
    hass: HomeAssistant,
    lms: MagicMock,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the children of a playlist are tracks that can be played."""
    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/browse_media",
            "entity_id": "media_player.test_player",
            "media_content_id": FAKE_VALID_ITEM_ID,
            "media_content_type": MediaType.PLAYLIST,
        }
    )
    response = await client.receive_json()
    assert response["success"]
    child = response["result"]["children"][0]
    assert child["media_class"] == MediaClass.TRACK
    assert child["media_content_type"] == MediaType.TRACK
    assert child["media_content_id"] == FAKE_VALID_ITEM_ID
    assert not child["can_expand"]
    assert child["can_play"]

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.test_player",
            ATTR_MEDIA_CONTENT_TYPE: child["media_content_type"],
            ATTR_MEDIA_CONTENT_ID: child["media_content_id"],
        },
        blocking=True,
    )
    player = (await lms.async_get_players())[0]
    player.async_browse.assert_called_with(
        "titles", limit=ANY, browse_id=("track_id", FAKE_VALID_ITEM_ID)
    )
    player.async_load_playlist.assert_called_once()


async def test_async_browse_media_for_apps(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test browsing for app category."""
    with patch(
        "homeassistant.components.squeezebox.browse_media.is_internal_request",
        return_value=False,
    ):
        category = "Apps"
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

        # Look up a subitem
        await client.send_json(
            {
                "id": 2,
                "type": "media_player/browse_media",
                "entity_id": "media_player.test_player",
                "media_content_id": "",
                "media_content_type": "app-fakecommand",
            }
        )
        response = await client.receive_json()
        assert response["success"]
        search = response["result"]
        assert search["children"][0]["title"] == "Fake Item 1"
        assert "Fake Invalid Item 1" not in search


@pytest.mark.parametrize(
    ("category", "media_filter_classes"),
    [
        ("favorites", None),
        ("artists", None),
        ("albums", None),
        ("playlists", None),
        ("genres", None),
        ("new music", None),
        ("album artists", None),
        ("albums", [MediaClass.ALBUM]),
    ],
)
async def test_async_search_media(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    category: str,
    media_filter_classes: list[MediaClass] | None,
) -> None:
    """Test each category with subitems."""
    with patch(
        "homeassistant.components.squeezebox.browse_media.is_internal_request",
        return_value=False,
    ):
        client = await hass_ws_client()
        await client.send_json(
            {
                "id": 1,
                "type": "media_player/search_media",
                "entity_id": "media_player.test_player",
                "media_content_id": "",
                "media_content_type": category,
                "search_query": "Fake Item 1",
                "media_filter_classes": media_filter_classes,
            }
        )
        response = await client.receive_json()
        assert response["success"]
        category_level = response["result"]["result"]
        assert category_level[0]["title"] == "Fake Item 1"


@pytest.mark.parametrize(
    ("media_content_type", "category", "id_key", "first_item"),
    [
        pytest.param(
            MediaType.ARTIST,
            "artist",
            "artist_id",
            ("Love Album", MediaClass.ALBUM, MediaType.ALBUM, "1", True),
            id="artist",
        ),
        pytest.param(
            MediaType.GENRE,
            "genre",
            "genre_id",
            ("Love Band", MediaClass.ARTIST, MediaType.ARTIST, "1", True),
            id="genre",
        ),
    ],
)
async def test_async_search_media_in_container(
    hass: HomeAssistant,
    lms: MagicMock,
    hass_ws_client: WebSocketGenerator,
    media_content_type: MediaType,
    category: str,
    id_key: str,
    first_item: tuple[str, MediaClass, MediaType, str, bool],
) -> None:
    """Test a search inside an artist or genre also matches track titles."""

    async def mock_browse(
        category: str,
        limit: int,
        browse_id: tuple[str, str] | None = None,
        search_query: str | None = None,
    ) -> dict[str, Any]:
        items = {
            "titles": [{"id": "2", "title": "Love Song"}],
        }.get(category, [{"id": "1", "title": first_item[0]}])
        return {"title": category, "items": items}

    player = (await lms.async_get_players())[0]
    player.async_browse.side_effect = mock_browse

    client = await hass_ws_client()
    await client.send_json(
        {
            "id": 1,
            "type": "media_player/search_media",
            "entity_id": "media_player.test_player",
            "media_content_id": "42",
            "media_content_type": media_content_type,
            "search_query": "love",
        }
    )
    response = await client.receive_json()
    assert response["success"]
    assert [
        (
            item["title"],
            item["media_class"],
            item["media_content_type"],
            item["media_content_id"],
            item["can_search"],
        )
        for item in response["result"]["result"]
    ] == [
        first_item,
        ("Love Song", MediaClass.TRACK, MediaType.TRACK, "2", False),
    ]
    assert player.async_browse.call_args_list == [
        call(category, limit=ANY, browse_id=(id_key, "42"), search_query="love"),
        call("titles", limit=ANY, browse_id=(id_key, "42"), search_query="love"),
    ]


async def test_async_search_media_invalid_filter(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test search_media action with invalid media_filter_class."""
    with patch(
        "homeassistant.components.squeezebox.browse_media.is_internal_request",
        return_value=False,
    ):
        client = await hass_ws_client()
        await client.send_json(
            {
                "id": 1,
                "type": "media_player/search_media",
                "entity_id": "media_player.test_player",
                "media_content_id": "",
                "media_content_type": "albums",
                "search_query": "Fake Item 1",
                "media_filter_classes": "movie",
            }
        )
        response = await client.receive_json()
        assert response["success"]
        assert len(response["result"]["result"]) == 0


@pytest.mark.parametrize(
    "media_content_type",
    [
        pytest.param("Fake Type", id="unknown"),
        pytest.param("artist tracks", id="internal_artist"),
        pytest.param("genre tracks", id="internal_genre"),
    ],
)
async def test_async_search_media_invalid_type(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    media_content_type: str,
) -> None:
    """Test search_media action with invalid media_content_type."""
    with patch(
        "homeassistant.components.squeezebox.browse_media.is_internal_request",
        return_value=False,
    ):
        client = await hass_ws_client()
        await client.send_json(
            {
                "id": 1,
                "type": "media_player/search_media",
                "entity_id": "media_player.test_player",
                "media_content_id": "",
                "media_content_type": media_content_type,
                "search_query": "Fake Item 1",
            },
        )
        response = await client.receive_json()
        assert not response["success"]
        err_message = "If specified, Media content type must be one of"
        assert err_message in response["error"]["message"]
        assert "artist tracks" not in response["error"]["message"]
        assert "genre tracks" not in response["error"]["message"]


async def test_async_search_media_not_found(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test trying to play an item that doesn't exist."""
    with patch(
        "homeassistant.components.squeezebox.browse_media.is_internal_request",
        return_value=False,
    ):
        client = await hass_ws_client()
        await client.send_json(
            {
                "id": 1,
                "type": "media_player/search_media",
                "entity_id": "media_player.test_player",
                "media_content_id": "",
                "media_content_type": "",
                "search_query": "Unknown Item",
            },
        )
        response = await client.receive_json()

        assert len(response["result"]["result"]) == 0


async def test_generate_playlist_for_app(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the generate_playlist for app-fakecommand media type."""
    with patch(
        "homeassistant.components.squeezebox.browse_media.is_internal_request",
        return_value=False,
    ):
        category = "Apps"
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

        try:
            await hass.services.async_call(
                MEDIA_PLAYER_DOMAIN,
                SERVICE_PLAY_MEDIA,
                {
                    ATTR_ENTITY_ID: "media_player.test_player",
                    ATTR_MEDIA_CONTENT_TYPE: "app-fakecommand",
                    ATTR_MEDIA_CONTENT_ID: FAKE_VALID_ITEM_ID,
                },
                blocking=True,
            )
        except BrowseError:
            pytest.fail("generate_playlist fails for app")


async def test_async_browse_tracks(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test tracks (no subitems)."""
    with patch(
        "homeassistant.components.squeezebox.browse_media.is_internal_request",
        return_value=True,
    ):
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
        assert len(tracks["children"]) == 4


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
    )


async def test_play_browse_item_nonexistent(
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


async def test_synthetic_thumbnail_item_ids(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test synthetic ID generation and url caching for items without stable IDs."""
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
                "media_content_type": "apps",
            }
        )
        response = await client.receive_json()
        assert response["success"]

        children = response["result"]["children"]
        assert len(children) > 0
        for child in children:
            if thumbnail := child.get("thumbnail"):
                assert not thumbnail.startswith("http://lms.internal")
                assert thumbnail.startswith("/api/media_player_proxy/")

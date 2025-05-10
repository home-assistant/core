"""Test the media browser interface."""

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
    ("category", "child_count"),
    [
        ("favorites", 4),
        ("artists", 4),
        ("albums", 4),
        ("playlists", 4),
        ("genres", 4),
        ("new music", 4),
        ("album artists", 4),
        ("apps", 3),
        ("radios", 3),
    ],
)
async def test_async_browse_media_with_subitems(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    category: str,
    child_count: int,
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
    ("category", "child_count"),
    [
        ("favorites", 1),
        ("artists", 1),
        ("albums", 1),
        ("playlists", 1),
        ("genres", 1),
        ("new music", 1),
        ("album artists", 1),
    ],
)
async def test_async_search_media(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
    category: str,
    child_count: int,
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
            }
        )
        response = await client.receive_json()
        assert response["success"]
        category_level = response["result"]["result"]
        assert category_level[0]["title"] == "Fake Item 1"


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

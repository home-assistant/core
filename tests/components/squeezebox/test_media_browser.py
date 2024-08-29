"""Test the media browser interface."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.media_player import BrowseError, BrowseMedia, MediaType
from homeassistant.components.squeezebox import DOMAIN
from homeassistant.components.squeezebox.browse_media import (
    LIBRARY,
    MEDIA_TYPE_TO_SQUEEZEBOX,
    SQUEEZEBOX_ID_BY_TYPE,
    build_item_response,
    library_payload,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Fixture for setting up the component."""
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.asyncio
async def test_async_browse_media(hass: HomeAssistant) -> None:
    """Test the async_browse_media function."""
    entity = AsyncMock()
    entity.hass = AsyncMock()
    player = AsyncMock()

    # Mock the player.async_browse method
    async def mock_async_browse(
        media_type: MediaType, limit: int, browse_id: tuple or None = None
    ) -> dict or None:
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

    player.async_browse.side_effect = mock_async_browse

    # Test the root level
    root = await library_payload(hass, player)
    assert type(root) is BrowseMedia
    for idx, item in enumerate(root.as_dict()["children"]):
        assert item["title"] == LIBRARY[idx]

    # Test each category
    for category in LIBRARY:
        with patch(
            "homeassistant.helpers.network.is_internal_request",
            return_value=True,
        ):
            category_level = await build_item_response(
                entity, player, {"search_type": category, "search_id": None}
            )
            assert type(root) is BrowseMedia
            assert (
                category_level.as_dict()["title"] == MEDIA_TYPE_TO_SQUEEZEBOX[category]
            )
            assert category_level.as_dict()["children"][0]["title"] == "Fake Item 1"
            search_type = category_level.as_dict()["children"][0]["media_content_type"]
            search_id = category_level.as_dict()["children"][0]["media_content_id"]
            if search_type is not MediaType.TRACK:  # we don't browse a track
                search = await build_item_response(
                    entity, player, {"search_type": search_type, "search_id": search_id}
                )
            assert search.as_dict()["title"] == "Fake Item 1"

    # Search for a non-existent item and assert BrowseError is raised
    with pytest.raises(BrowseError):
        search = await build_item_response(
            entity, player, {"search_type": MediaType.ALBUM, "search_id": "0"}
        )

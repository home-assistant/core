"""Setup the squeezebox tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.media_player import MediaType
from homeassistant.components.squeezebox import const
from homeassistant.components.squeezebox.browse_media import (
    MEDIA_TYPE_TO_SQUEEZEBOX,
    SQUEEZEBOX_ID_BY_TYPE,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_PORT = "9000"
TEST_USE_HTTPS = False
SERVER_UUID = "12345678-1234-1234-1234-123456789012"
TEST_MAC = "aa:bb:cc:dd:ee:ff"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.squeezebox.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Add the squeezebox mock config entry to hass."""
    config_entry = MockConfigEntry(
        domain=const.DOMAIN,
        unique_id=SERVER_UUID,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            const.CONF_HTTPS: TEST_USE_HTTPS,
        },
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def mock_async_browse(
    media_type: MediaType, limit: int, browse_id: tuple | None = None
) -> dict | None:
    """Mock the async_browse method of pysqueezebox.Player."""
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


@pytest.fixture
def lms() -> MagicMock:
    """Mock a Lyrion Media Server with one mock player attached."""
    lms = MagicMock()
    player = MagicMock()
    player.player_id = TEST_MAC
    player.name = "Test Player"
    player.power = False
    player.async_browse = AsyncMock(side_effect=mock_async_browse)
    player.async_load_playlist = AsyncMock()
    player.async_update = AsyncMock()
    player.generate_image_url_from_track_id = MagicMock(
        return_value="http://lms.internal:9000/html/images/favorites.png"
    )
    lms.async_get_players = AsyncMock(return_value=[player])
    lms.async_query = AsyncMock(return_value={"uuid": format_mac(TEST_MAC)})
    return lms

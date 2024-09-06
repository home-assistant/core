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
from homeassistant.util.uuid import random_uuid_hex

from tests.common import MockConfigEntry

TEST_HOST = "1.2.3.4"
TEST_PORT = "9000"
TEST_USE_HTTPS = False
SERVER_UUID = "12345678-1234-1234-1234-123456789012"
TEST_MAC = "aa:bb:cc:dd:ee:ff"
TEST_PLAYER_NAME = "Test Player"
TEST_SERVER_NAME = "Test Server"
FAKE_VALID_ITEM_ID = "1234"
FAKE_INVALID_ITEM_ID = "4321"


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
            "id": FAKE_VALID_ITEM_ID,
            "hasitems": False,
            "item_type": child_types[media_type],
            "artwork_track_id": "b35bb9e9",
            "url": "file:///var/lib/squeezeboxserver/music/track_1.mp3",
        },
        {
            "title": "Fake Item 2",
            "id": FAKE_VALID_ITEM_ID + "_2",
            "hasitems": media_type == "favorites",
            "item_type": child_types[media_type],
            "image_url": "http://lms.internal:9000/html/images/favorites.png",
            "url": "file:///var/lib/squeezeboxserver/music/track_2.mp3",
        },
        {
            "title": "Fake Item 3",
            "id": FAKE_VALID_ITEM_ID + "_3",
            "hasitems": media_type == "favorites",
            "album_id": FAKE_VALID_ITEM_ID if media_type == "favorites" else None,
            "url": "file:///var/lib/squeezeboxserver/music/track_3.mp3",
        },
    ]

    if browse_id:
        search_type, search_id = browse_id
        if search_id:
            if search_type == "playlist_id":
                return (
                    {
                        "title": "Fake Item 1",
                        "items": fake_items,
                    }
                    if search_id == FAKE_VALID_ITEM_ID
                    else None
                )
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
def player() -> MagicMock:
    """Return a mock player."""
    return mock_pysqueezebox_player()


@pytest.fixture
def player_factory() -> MagicMock:
    """Return a factory for creating mock players."""
    return mock_pysqueezebox_player


def mock_pysqueezebox_player() -> MagicMock:
    """Mock a Lyrion Media Server player."""
    with patch("pysqueezebox.Player", autospec=True) as mock_player:
        mock_player.async_browse = AsyncMock(side_effect=mock_async_browse)
        mock_player.generate_image_url_from_track_id = MagicMock(
            return_value="http://lms.internal:9000/html/images/favorites.png"
        )
        mock_player.name = TEST_PLAYER_NAME
        mock_player.player_id = random_uuid_hex()
        return mock_player


@pytest.fixture
def lms_factory(player_factory: MagicMock) -> MagicMock:
    """Return a factory for creating mock Lyrion Media Servers with arbitrary number of players."""
    return lambda player_count: mock_pysqueezebox_server(player_factory, player_count)


@pytest.fixture
def lms(player_factory: MagicMock) -> MagicMock:
    """Mock a Lyrion Media Server with one mock player attached."""
    return mock_pysqueezebox_server(player_factory, 1, uuid=TEST_MAC)


def mock_pysqueezebox_server(
    player_factory: MagicMock, player_count: int, uuid: str | None = None
) -> MagicMock:
    """Create a mock Lyrion Media Server with the given number of mock players attached."""
    with patch("pysqueezebox.Server", autospec=True) as mock_lms:
        players = [player_factory() for _ in range(player_count)]
        mock_lms.async_get_players = AsyncMock(return_value=players)

        if not uuid:
            uuid = random_uuid_hex()

        mock_lms.uuid = uuid
        mock_lms.name = TEST_SERVER_NAME
        mock_lms.async_query = AsyncMock(return_value={"uuid": format_mac(uuid)})
        mock_lms.async_status = AsyncMock(return_value={"uuid": format_mac(uuid)})
        return mock_lms


async def configure_squeezebox(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    lms: MagicMock,
) -> None:
    """Configure a squeezebox config entry."""
    with (
        patch("homeassistant.components.squeezebox.Server", return_value=lms),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)


@pytest.fixture
async def configured_player(
    hass: HomeAssistant, config_entry: MockConfigEntry, lms: MagicMock
) -> MagicMock:
    """Fixture mocking calls to pysqueezebox Player from a configured squeezebox."""
    await configure_squeezebox(hass, config_entry, lms)
    return (await lms.async_get_players())[0]


@pytest.fixture
async def configured_players(
    hass: HomeAssistant, config_entry: MockConfigEntry, lms_factory: MagicMock
) -> list[MagicMock]:
    """Fixture mocking calls to two pysqueezebox Players from a configured squeezebox."""
    lms = lms_factory(2)
    await configure_squeezebox(hass, config_entry, lms)
    return await lms.async_get_players()

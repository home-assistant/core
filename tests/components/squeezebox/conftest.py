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
    return create_mock_player()


@pytest.fixture
def player_factory() -> MagicMock:
    """Return a factory for creating mock players."""
    return create_mock_player


def create_mock_player() -> MagicMock:
    """Mock a Lyrion Media Server player."""
    player = MagicMock()

    # set some default fake values for properties
    player.player_id = random_uuid_hex()
    player.current_index = 0
    player.mode = "stop"
    player.muting = False
    player.name = TEST_PLAYER_NAME
    player.playlist: list(dict(str, str)) | None = None
    player.power = True
    player.repeat = "none"
    player.shuffle = "none"
    player.time = 0
    player.volume = 10

    # mock pysqueezebox.Player methods
    player.async_browse = AsyncMock(side_effect=mock_async_browse)
    player.async_clear_playlist = AsyncMock(
        side_effect=lambda: setattr(player, "playlist", None)
    )
    player.async_index = AsyncMock(
        side_effect=lambda index: setattr(
            player,
            "current_index",
            player.current_index + int(index)
            if index.startswith(("+", "-"))
            else index,
        )
    )

    def async_load_playlist(playlist, cmd):
        if cmd == "add":
            if player.playlist is None:
                player.playlist = []
            player.playlist.extend(playlist)
        else:
            player.playlist = playlist
        player.current_index = 0
        player.url = player.playlist[0]

    player.async_load_playlist = AsyncMock(side_effect=async_load_playlist)
    player.async_load_url = AsyncMock(
        side_effect=lambda url, cmd: async_load_playlist([{"url": url}], cmd)
    )
    player.async_play = AsyncMock(side_effect=lambda: setattr(player, "mode", "play"))
    player.async_pause = AsyncMock(side_effect=lambda: setattr(player, "mode", "pause"))
    player.async_set_muting = AsyncMock(
        side_effect=lambda muting: setattr(player, "muting", muting)
    )
    player.async_set_power = AsyncMock(
        side_effect=lambda power: setattr(player, "power", power)
    )
    player.async_set_repeat = AsyncMock(
        side_effect=lambda repeat: setattr(player, "repeat", repeat)
    )
    player.async_set_shuffle = AsyncMock(
        side_effect=lambda shuffle: setattr(player, "shuffle", shuffle)
    )
    player.async_set_volume = AsyncMock(
        side_effect=lambda volume: setattr(
            player,
            "volume",
            player.volume + int(volume) if volume.startswith(("+", "-")) else volume,
        )
    )
    player.async_stop = AsyncMock(side_effect=lambda: setattr(player, "mode", "stop"))
    player.async_sync = AsyncMock()
    player.async_time = AsyncMock(
        side_effect=lambda time: setattr(player, "time", time)
    )
    player.async_toggle_pause = AsyncMock(
        side_effect=lambda: setattr(
            player, "mode", "play" if player.mode != "play" else "pause"
        )
    )
    player.async_query = AsyncMock(return_value="test result")
    player.async_update = AsyncMock()
    player.async_unsync = AsyncMock()
    player.generate_image_url_from_track_id = MagicMock(
        return_value="http://lms.internal:9000/html/images/favorites.png"
    )
    return player


@pytest.fixture
def lms_factory(player_factory: MagicMock) -> MagicMock:
    """Return a factory for creating mock Lyrion Media Servers with arbitrary number of players."""
    return lambda player_count: create_mock_lms(player_factory, player_count)


@pytest.fixture
def lms(player_factory: MagicMock) -> MagicMock:
    """Mock a Lyrion Media Server with one mock player attached."""
    return create_mock_lms(player_factory, 1, uuid=TEST_MAC)


def create_mock_lms(
    player_factory: MagicMock, player_count: int, uuid: str | None = None
) -> MagicMock:
    """Create a mock Lyrion Media Server with the given number of mock players attached."""
    lms = MagicMock()
    players = [player_factory() for _ in range(player_count)]
    lms.async_get_players = AsyncMock(return_value=players)

    if not uuid:
        uuid = random_uuid_hex()
    lms.async_query = AsyncMock(return_value={"uuid": format_mac(uuid)})
    lms.async_status = AsyncMock(return_value={"uuid": format_mac(uuid)})
    return lms


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

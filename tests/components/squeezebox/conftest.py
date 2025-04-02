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
from homeassistant.components.squeezebox.const import (
    STATUS_QUERY_LIBRARYNAME,
    STATUS_QUERY_MAC,
    STATUS_QUERY_UUID,
    STATUS_QUERY_VERSION,
    STATUS_SENSOR_INFO_TOTAL_ALBUMS,
    STATUS_SENSOR_INFO_TOTAL_ARTISTS,
    STATUS_SENSOR_INFO_TOTAL_DURATION,
    STATUS_SENSOR_INFO_TOTAL_GENRES,
    STATUS_SENSOR_INFO_TOTAL_SONGS,
    STATUS_SENSOR_LASTSCAN,
    STATUS_SENSOR_OTHER_PLAYER_COUNT,
    STATUS_SENSOR_PLAYER_COUNT,
    STATUS_SENSOR_RESCAN,
)
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

# from homeassistant.setup import async_setup_component
from tests.common import MockConfigEntry

CONF_VOLUME_STEP = "volume_step"
TEST_VOLUME_STEP = 10

TEST_HOST = "1.2.3.4"
TEST_PORT = "9000"
TEST_USE_HTTPS = False
SERVER_UUIDS = [
    "12345678-1234-1234-1234-123456789012",
    "87654321-4321-4321-4321-210987654321",
]
TEST_MAC = ["aa:bb:cc:dd:ee:ff", "ff:ee:dd:cc:bb:aa"]
TEST_PLAYER_NAME = "Test Player"
TEST_SERVER_NAME = "Test Server"
FAKE_VALID_ITEM_ID = "1234"
FAKE_INVALID_ITEM_ID = "4321"

FAKE_IP = "42.42.42.42"
FAKE_MAC = "deadbeefdead"
FAKE_UUID = "deadbeefdeadbeefbeefdeafbeef42"
FAKE_PORT = 9000
FAKE_VERSION = "42.0"

FAKE_QUERY_RESPONSE = {
    STATUS_QUERY_UUID: FAKE_UUID,
    STATUS_QUERY_MAC: FAKE_MAC,
    STATUS_QUERY_VERSION: FAKE_VERSION,
    STATUS_SENSOR_RESCAN: 1,
    STATUS_SENSOR_LASTSCAN: 0,
    STATUS_QUERY_LIBRARYNAME: "FakeLib",
    STATUS_SENSOR_INFO_TOTAL_ALBUMS: 4,
    STATUS_SENSOR_INFO_TOTAL_ARTISTS: 2,
    STATUS_SENSOR_INFO_TOTAL_DURATION: 500,
    STATUS_SENSOR_INFO_TOTAL_GENRES: 1,
    STATUS_SENSOR_INFO_TOTAL_SONGS: 42,
    STATUS_SENSOR_PLAYER_COUNT: 10,
    STATUS_SENSOR_OTHER_PLAYER_COUNT: 0,
    "players_loop": [
        {
            "isplaying": 0,
            "name": "SqueezeLite-HA-Addon",
            "seq_no": 0,
            "modelname": "SqueezeLite-HA-Addon",
            "playerindex": "status",
            "model": "squeezelite",
            "uuid": FAKE_UUID,
            "canpoweroff": 1,
            "ip": "192.168.78.86:57700",
            "displaytype": "none",
            "playerid": "f9:23:cd:37:c5:ff",
            "power": 0,
            "isplayer": 1,
            "connected": 1,
            "firmware": "v2.0.0-1488",
        }
    ],
    "count": 1,
}


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
        unique_id=SERVER_UUIDS[0],
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            const.CONF_HTTPS: TEST_USE_HTTPS,
        },
        options={
            CONF_VOLUME_STEP: TEST_VOLUME_STEP,
        },
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def mock_async_play_announcement(media_id: str) -> bool:
    """Mock the announcement."""
    return True


async def mock_async_browse(
    media_type: MediaType, limit: int, browse_id: tuple | None = None
) -> dict | None:
    """Mock the async_browse method of pysqueezebox.Player."""
    child_types = {
        "favorites": "favorites",
        "new music": "album",
        "album artists": "artists",
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
        "apps": "app",
        "radios": "app",
        "app-fakecommand": "track",
    }
    fake_items = [
        {
            "title": "Fake Item 1",
            "id": FAKE_VALID_ITEM_ID,
            "hasitems": False,
            "isaudio": True,
            "item_type": child_types[media_type],
            "artwork_track_id": "b35bb9e9",
            "url": "file:///var/lib/squeezeboxserver/music/track_1.mp3",
            "cmd": "fakecommand",
            "icon": "plugins/Qobuz/html/images/qobuz.png",
        },
        {
            "title": "Fake Item 2",
            "id": FAKE_VALID_ITEM_ID + "_2",
            "hasitems": media_type == "favorites",
            "isaudio": False,
            "item_type": child_types[media_type],
            "image_url": "http://lms.internal:9000/html/images/favorites.png",
            "url": "file:///var/lib/squeezeboxserver/music/track_2.mp3",
            "cmd": "fakecommand",
            "icon": "plugins/Qobuz/html/images/qobuz.png",
        },
        {
            "title": "Fake Item 3",
            "id": FAKE_VALID_ITEM_ID + "_3",
            "hasitems": media_type == "favorites",
            "isaudio": True,
            "album_id": FAKE_VALID_ITEM_ID if media_type == "favorites" else None,
            "url": "file:///var/lib/squeezeboxserver/music/track_3.mp3",
            "cmd": "fakecommand",
            "icon": "plugins/Qobuz/html/images/qobuz.png",
        },
        {
            "title": "Fake Invalid Item 1",
            "id": FAKE_VALID_ITEM_ID + "invalid_3",
            "hasitems": media_type == "favorites",
            "isaudio": True,
            "album_id": FAKE_VALID_ITEM_ID if media_type == "favorites" else None,
            "url": "file:///var/lib/squeezeboxserver/music/track_3.mp3",
            "cmd": "fakecommand",
            "icon": "plugins/Qobuz/html/images/qobuz.png",
            "type": "text",
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
    if (
        media_type in MEDIA_TYPE_TO_SQUEEZEBOX.values()
        or media_type == "app-fakecommand"
    ):
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


def mock_pysqueezebox_player(uuid: str) -> MagicMock:
    """Mock a Lyrion Media Server player."""
    with patch(
        "homeassistant.components.squeezebox.Player", autospec=True
    ) as mock_player:
        mock_player.async_browse = AsyncMock(side_effect=mock_async_browse)
        mock_player.generate_image_url_from_track_id = MagicMock(
            return_value="http://lms.internal:9000/html/images/favorites.png"
        )
        mock_player.set_announce_volume = MagicMock(return_value=True)
        mock_player.set_announce_timeout = MagicMock(return_value=True)
        mock_player.async_play_announcement = AsyncMock(
            side_effect=mock_async_play_announcement
        )
        mock_player.generate_image_url = MagicMock(
            return_value="http://lms.internal:9000/html/images/favorites.png"
        )
        mock_player.name = TEST_PLAYER_NAME
        mock_player.player_id = uuid
        mock_player.mode = "stop"
        mock_player.playlist = None
        mock_player.album = None
        mock_player.artist = None
        mock_player.remote_title = None
        mock_player.title = None
        mock_player.image_url = None
        mock_player.model = "SqueezeLite"
        mock_player.creator = "Ralph Irving & Adrian Smith"

        return mock_player


@pytest.fixture
def lms_factory(player_factory: MagicMock) -> MagicMock:
    """Return a factory for creating mock Lyrion Media Servers with arbitrary number of players."""
    return lambda player_count, uuid: mock_pysqueezebox_server(
        player_factory, player_count, uuid
    )


@pytest.fixture
def lms(player_factory: MagicMock) -> MagicMock:
    """Mock a Lyrion Media Server with one mock player attached."""
    return mock_pysqueezebox_server(player_factory, 1, uuid=TEST_MAC[0])


def mock_pysqueezebox_server(
    player_factory: MagicMock, player_count: int, uuid: str
) -> MagicMock:
    """Create a mock Lyrion Media Server with the given number of mock players attached."""
    with patch("homeassistant.components.squeezebox.Server", autospec=True) as mock_lms:
        players = [player_factory(TEST_MAC[index]) for index in range(player_count)]
        mock_lms.async_get_players = AsyncMock(return_value=players)

        mock_lms.uuid = uuid
        mock_lms.name = TEST_SERVER_NAME
        mock_lms.async_query = AsyncMock(return_value={"uuid": format_mac(uuid)})
        mock_lms.async_status = AsyncMock(return_value={"uuid": format_mac(uuid)})
        return mock_lms


async def configure_squeezebox_media_player_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    lms: MagicMock,
) -> None:
    """Configure a squeezebox config entry with appropriate mocks for media_player."""
    with (
        patch(
            "homeassistant.components.squeezebox.PLATFORMS",
            [Platform.MEDIA_PLAYER],
        ),
        patch("homeassistant.components.squeezebox.Server", return_value=lms),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)


async def configure_squeezebox_media_player_button_platform(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    lms: MagicMock,
) -> None:
    """Configure a squeezebox config entry with appropriate mocks for media_player."""
    with (
        patch(
            "homeassistant.components.squeezebox.PLATFORMS",
            [Platform.BUTTON],
        ),
        patch("homeassistant.components.squeezebox.Server", return_value=lms),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)


@pytest.fixture
async def configured_player(
    hass: HomeAssistant, config_entry: MockConfigEntry, lms: MagicMock
) -> MagicMock:
    """Fixture mocking calls to pysqueezebox Player from a configured squeezebox."""
    await configure_squeezebox_media_player_platform(hass, config_entry, lms)
    return (await lms.async_get_players())[0]


@pytest.fixture
async def configured_player_with_button(
    hass: HomeAssistant, config_entry: MockConfigEntry, lms: MagicMock
) -> MagicMock:
    """Fixture mocking calls to pysqueezebox Player from a configured squeezebox."""
    await configure_squeezebox_media_player_button_platform(hass, config_entry, lms)
    return (await lms.async_get_players())[0]


@pytest.fixture
async def configured_players(
    hass: HomeAssistant, config_entry: MockConfigEntry, lms_factory: MagicMock
) -> list[MagicMock]:
    """Fixture mocking calls to two pysqueezebox Players from a configured squeezebox."""
    lms = lms_factory(2, uuid=SERVER_UUIDS[0])
    await configure_squeezebox_media_player_platform(hass, config_entry, lms)
    return await lms.async_get_players()

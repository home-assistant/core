"""Configuration for HEOS tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, Mock, patch

from pyheos import (
    CONTROLS_ALL,
    Heos,
    HeosGroup,
    HeosOptions,
    HeosPlayer,
    LineOutLevelType,
    MediaItem,
    MediaType,
    NetworkType,
    PlayerUpdateResult,
    PlayState,
    RepeatType,
    const,
)
import pytest
import pytest_asyncio

from homeassistant.components.heos import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_DEVICE_TYPE,
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_MANUFACTURER,
    ATTR_UPNP_MODEL_NAME,
    ATTR_UPNP_MODEL_NUMBER,
    ATTR_UPNP_SERIAL,
    ATTR_UPNP_UDN,
    SsdpServiceInfo,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture() -> MockConfigEntry:
    """Create a mock HEOS config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
        title="HEOS System (via 127.0.0.1)",
        unique_id=DOMAIN,
    )


@pytest.fixture(name="config_entry_options")
def config_entry_options_fixture() -> MockConfigEntry:
    """Create a mock HEOS config entry with options."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
        title="HEOS System (via 127.0.0.1)",
        options={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        unique_id=DOMAIN,
    )


@pytest_asyncio.fixture(name="controller", autouse=True)
async def controller_fixture(
    players: dict[int, HeosPlayer],
    favorites: dict[int, MediaItem],
    input_sources: list[MediaItem],
    playlists: list[MediaItem],
    change_data: PlayerUpdateResult,
    group: dict[int, HeosGroup],
) -> AsyncIterator[Heos]:
    """Create a mock Heos controller fixture."""
    mock_heos = Heos(HeosOptions(host="127.0.0.1"))
    for player in players.values():
        player.heos = mock_heos
    mock_heos.connect = AsyncMock()
    mock_heos.disconnect = AsyncMock()
    mock_heos.sign_in = AsyncMock()
    mock_heos.sign_out = AsyncMock()
    mock_heos.get_players = AsyncMock(return_value=players)
    mock_heos._players = players
    mock_heos.get_favorites = AsyncMock(return_value=favorites)
    mock_heos.get_input_sources = AsyncMock(return_value=input_sources)
    mock_heos.get_playlists = AsyncMock(return_value=playlists)
    mock_heos.load_players = AsyncMock(return_value=change_data)
    mock_heos._signed_in_username = "user@user.com"
    mock_heos.get_groups = AsyncMock(return_value=group)
    mock_heos._groups = group
    mock_heos.set_group = AsyncMock(return_value=None)
    new_mock = Mock(return_value=mock_heos)
    mock_heos.new_mock = new_mock
    with (
        patch("homeassistant.components.heos.coordinator.Heos", new=new_mock),
        patch("homeassistant.components.heos.config_flow.Heos", new=new_mock),
    ):
        yield mock_heos


@pytest.fixture(name="players")
def players_fixture(quick_selects: dict[int, str]) -> dict[int, HeosPlayer]:
    """Create two mock HeosPlayers."""
    players = {}
    for i in (1, 2):
        player = HeosPlayer(
            player_id=i,
            group_id=999,
            name="Test Player" if i == 1 else f"Test Player {i}",
            model="HEOS Drive HS2" if i == 1 else "Speaker",
            serial="123456",
            version="1.0.0",
            line_out=LineOutLevelType.VARIABLE,
            is_muted=False,
            available=True,
            state=PlayState.STOP,
            ip_address=f"127.0.0.{i}",
            network=NetworkType.WIRED,
            shuffle=False,
            repeat=RepeatType.OFF,
            volume=25,
            heos=None,
        )
        player.now_playing_media = Mock()
        player.now_playing_media.supported_controls = CONTROLS_ALL
        player.now_playing_media.album_id = 1
        player.now_playing_media.queue_id = 1
        player.now_playing_media.source_id = 1
        player.now_playing_media.station = "Station Name"
        player.now_playing_media.type = "Station"
        player.now_playing_media.album = "Album"
        player.now_playing_media.artist = "Artist"
        player.now_playing_media.media_id = "1"
        player.now_playing_media.duration = None
        player.now_playing_media.current_position = None
        player.now_playing_media.image_url = "http://"
        player.now_playing_media.song = "Song"
        player.add_to_queue = AsyncMock()
        player.clear_queue = AsyncMock()
        player.get_quick_selects = AsyncMock(return_value=quick_selects)
        player.mute = AsyncMock()
        player.pause = AsyncMock()
        player.play = AsyncMock()
        player.play_media = AsyncMock()
        player.play_next = AsyncMock()
        player.play_previous = AsyncMock()
        player.play_preset_station = AsyncMock()
        player.play_quick_select = AsyncMock()
        player.play_url = AsyncMock()
        player.set_mute = AsyncMock()
        player.set_play_mode = AsyncMock()
        player.set_quick_select = AsyncMock()
        player.set_volume = AsyncMock()
        player.stop = AsyncMock()
        player.unmute = AsyncMock()
        players[player.player_id] = player
    return players


@pytest.fixture(name="group")
def group_fixture() -> dict[int, HeosGroup]:
    """Create a HEOS group consisting of two players."""
    group = HeosGroup(
        name="Group", group_id=999, lead_player_id=1, member_player_ids=[2]
    )
    return {group.group_id: group}


@pytest.fixture(name="favorites")
def favorites_fixture() -> dict[int, MediaItem]:
    """Create favorites fixture."""
    station = MediaItem(
        source_id=const.MUSIC_SOURCE_PANDORA,
        name="Today's Hits Radio",
        media_id="123456789",
        type=MediaType.STATION,
        playable=True,
        browsable=False,
        image_url="",
        heos=None,
    )
    radio = MediaItem(
        source_id=const.MUSIC_SOURCE_TUNEIN,
        name="Classical MPR (Classical Music)",
        media_id="s1234",
        type=MediaType.STATION,
        playable=True,
        browsable=False,
        image_url="",
        heos=None,
    )
    return {1: station, 2: radio}


@pytest.fixture(name="input_sources")
def input_sources_fixture() -> list[MediaItem]:
    """Create a set of input sources for testing."""
    return [
        MediaItem(
            source_id=const.MUSIC_SOURCE_AUX_INPUT,
            name="HEOS Drive - Line In 1",
            media_id=const.INPUT_AUX_IN_1,
            type=MediaType.STATION,
            playable=True,
            browsable=False,
            image_url="",
            heos=None,
        ),
        MediaItem(
            source_id=const.MUSIC_SOURCE_AUX_INPUT,
            name="Speaker - Line In 1",
            media_id=const.INPUT_AUX_IN_1,
            type=MediaType.STATION,
            playable=True,
            browsable=False,
            image_url="",
            heos=None,
        ),
    ]


@pytest.fixture(name="discovery_data")
def discovery_data_fixture() -> SsdpServiceInfo:
    """Return mock discovery data for testing."""
    return SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_location="http://127.0.0.1:60006/upnp/desc/aios_device/aios_device.xml",
        upnp={
            ATTR_UPNP_DEVICE_TYPE: "urn:schemas-denon-com:device:AiosDevice:1",
            ATTR_UPNP_FRIENDLY_NAME: "Office",
            ATTR_UPNP_MANUFACTURER: "Denon",
            ATTR_UPNP_MODEL_NAME: "HEOS Drive",
            ATTR_UPNP_MODEL_NUMBER: "DWSA-10 4.0",
            ATTR_UPNP_SERIAL: None,
            ATTR_UPNP_UDN: "uuid:e61de70c-2250-1c22-0080-0005cdf512be",
        },
    )


@pytest.fixture(name="discovery_data_bedroom")
def discovery_data_fixture_bedroom() -> SsdpServiceInfo:
    """Return mock discovery data for testing."""
    return SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_location="http://127.0.0.2:60006/upnp/desc/aios_device/aios_device.xml",
        upnp={
            ATTR_UPNP_DEVICE_TYPE: "urn:schemas-denon-com:device:AiosDevice:1",
            ATTR_UPNP_FRIENDLY_NAME: "Bedroom",
            ATTR_UPNP_MANUFACTURER: "Denon",
            ATTR_UPNP_MODEL_NAME: "HEOS Drive",
            ATTR_UPNP_MODEL_NUMBER: "DWSA-10 4.0",
            ATTR_UPNP_SERIAL: None,
            ATTR_UPNP_UDN: "uuid:e61de70c-2250-1c22-0080-0005cdf512be",
        },
    )


@pytest.fixture(name="quick_selects")
def quick_selects_fixture() -> dict[int, str]:
    """Create a dict of quick selects for testing."""
    return {
        1: "Quick Select 1",
        2: "Quick Select 2",
        3: "Quick Select 3",
        4: "Quick Select 4",
        5: "Quick Select 5",
        6: "Quick Select 6",
    }


@pytest.fixture(name="playlists")
def playlists_fixture() -> list[MediaItem]:
    """Create favorites fixture."""
    playlist = MediaItem(
        source_id=const.MUSIC_SOURCE_PLAYLISTS,
        name="Awesome Music",
        type=MediaType.PLAYLIST,
        playable=True,
        browsable=True,
        image_url="",
        heos=None,
    )
    return [playlist]


@pytest.fixture(name="change_data")
def change_data_fixture() -> PlayerUpdateResult:
    """Create player change data for testing."""
    return PlayerUpdateResult()


@pytest.fixture(name="change_data_mapped_ids")
def change_data_mapped_ids_fixture() -> PlayerUpdateResult:
    """Create player change data for testing."""
    return PlayerUpdateResult(updated_player_ids={1: 101})

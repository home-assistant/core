"""Configuration for HEOS tests."""

from __future__ import annotations

from collections.abc import Sequence
from unittest.mock import AsyncMock, Mock, patch

from pyheos import (
    CONTROLS_ALL,
    Dispatcher,
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

from homeassistant.components import ssdp
from homeassistant.components.heos import (
    CONF_PASSWORD,
    DOMAIN,
    ControllerManager,
    GroupManager,
    HeosRuntimeData,
    SourceManager,
)
from homeassistant.const import CONF_HOST, CONF_USERNAME

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture(heos_runtime_data):
    """Create a mock HEOS config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
        title="HEOS System (via 127.0.0.1)",
        unique_id=DOMAIN,
    )
    entry.runtime_data = heos_runtime_data
    return entry


@pytest.fixture(name="config_entry_options")
def config_entry_options_fixture(heos_runtime_data):
    """Create a mock HEOS config entry with options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "127.0.0.1"},
        title="HEOS System (via 127.0.0.1)",
        options={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        unique_id=DOMAIN,
    )
    entry.runtime_data = heos_runtime_data
    return entry


@pytest.fixture(name="heos_runtime_data")
def heos_runtime_data_fixture(controller_manager, players):
    """Create a mock HeosRuntimeData fixture."""
    return HeosRuntimeData(
        controller_manager, Mock(GroupManager), Mock(SourceManager), players
    )


@pytest.fixture(name="controller_manager")
def controller_manager_fixture(controller):
    """Create a mock controller manager fixture."""
    mock_controller_manager = Mock(ControllerManager)
    mock_controller_manager.controller = controller
    return mock_controller_manager


@pytest.fixture(name="controller")
def controller_fixture(
    players, favorites, input_sources, playlists, change_data, dispatcher, group
):
    """Create a mock Heos controller fixture."""
    mock_heos = Heos(HeosOptions(host="127.0.0.1", dispatcher=dispatcher))
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
    mock_heos.create_group = AsyncMock(return_value=None)
    new_mock = Mock(return_value=mock_heos)
    mock_heos.new_mock = new_mock
    with (
        patch("homeassistant.components.heos.Heos", new=new_mock),
        patch("homeassistant.components.heos.config_flow.Heos", new=new_mock),
    ):
        yield mock_heos


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {DOMAIN: {CONF_HOST: "127.0.0.1"}}


@pytest.fixture(name="players")
def player_fixture(quick_selects):
    """Create two mock HeosPlayers."""
    players = {}
    for i in (1, 2):
        player = HeosPlayer(
            player_id=i,
            name="Test Player" if i == 1 else f"Test Player {i}",
            model="Test Model",
            serial="",
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
        player.play_input_source = AsyncMock()
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
def group_fixture():
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
def input_sources_fixture() -> Sequence[MediaItem]:
    """Create a set of input sources for testing."""
    source = MediaItem(
        source_id=1,
        name="HEOS Drive - Line In 1",
        media_id=const.INPUT_AUX_IN_1,
        type=MediaType.STATION,
        playable=True,
        browsable=False,
        image_url="",
        heos=None,
    )
    return [source]


@pytest_asyncio.fixture(name="dispatcher")
async def dispatcher_fixture() -> Dispatcher:
    """Create a dispatcher for testing."""
    return Dispatcher()


@pytest.fixture(name="discovery_data")
def discovery_data_fixture() -> dict:
    """Return mock discovery data for testing."""
    return ssdp.SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_location="http://127.0.0.1:60006/upnp/desc/aios_device/aios_device.xml",
        upnp={
            ssdp.ATTR_UPNP_DEVICE_TYPE: "urn:schemas-denon-com:device:AiosDevice:1",
            ssdp.ATTR_UPNP_FRIENDLY_NAME: "Office",
            ssdp.ATTR_UPNP_MANUFACTURER: "Denon",
            ssdp.ATTR_UPNP_MODEL_NAME: "HEOS Drive",
            ssdp.ATTR_UPNP_MODEL_NUMBER: "DWSA-10 4.0",
            ssdp.ATTR_UPNP_SERIAL: None,
            ssdp.ATTR_UPNP_UDN: "uuid:e61de70c-2250-1c22-0080-0005cdf512be",
        },
    )


@pytest.fixture(name="discovery_data_bedroom")
def discovery_data_fixture_bedroom() -> dict:
    """Return mock discovery data for testing."""
    return ssdp.SsdpServiceInfo(
        ssdp_usn="mock_usn",
        ssdp_st="mock_st",
        ssdp_location="http://127.0.0.2:60006/upnp/desc/aios_device/aios_device.xml",
        upnp={
            ssdp.ATTR_UPNP_DEVICE_TYPE: "urn:schemas-denon-com:device:AiosDevice:1",
            ssdp.ATTR_UPNP_FRIENDLY_NAME: "Bedroom",
            ssdp.ATTR_UPNP_MANUFACTURER: "Denon",
            ssdp.ATTR_UPNP_MODEL_NAME: "HEOS Drive",
            ssdp.ATTR_UPNP_MODEL_NUMBER: "DWSA-10 4.0",
            ssdp.ATTR_UPNP_SERIAL: None,
            ssdp.ATTR_UPNP_UDN: "uuid:e61de70c-2250-1c22-0080-0005cdf512be",
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
def playlists_fixture() -> Sequence[MediaItem]:
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
def change_data_fixture() -> dict:
    """Create player change data for testing."""
    return PlayerUpdateResult()


@pytest.fixture(name="change_data_mapped_ids")
def change_data_mapped_ids_fixture() -> dict:
    """Create player change data for testing."""
    return PlayerUpdateResult(updated_player_ids={1: 101})

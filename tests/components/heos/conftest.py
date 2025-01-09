"""Configuration for HEOS tests."""

from __future__ import annotations

from collections.abc import Sequence
from unittest.mock import Mock, patch

from pyheos import Dispatcher, Heos, HeosGroup, HeosPlayer, MediaItem, const
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
    mock_heos = Mock(Heos)
    for player in players.values():
        player.heos = mock_heos
    mock_heos.return_value = mock_heos
    mock_heos.dispatcher = dispatcher
    mock_heos.get_players.return_value = players
    mock_heos.players = players
    mock_heos.get_favorites.return_value = favorites
    mock_heos.get_input_sources.return_value = input_sources
    mock_heos.get_playlists.return_value = playlists
    mock_heos.load_players.return_value = change_data
    mock_heos.is_signed_in = True
    mock_heos.signed_in_username = "user@user.com"
    mock_heos.connection_state = const.STATE_CONNECTED
    mock_heos.get_groups.return_value = group
    mock_heos.create_group.return_value = None

    with (
        patch("homeassistant.components.heos.Heos", new=mock_heos),
        patch("homeassistant.components.heos.config_flow.Heos", new=mock_heos),
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
        player = Mock(HeosPlayer)
        player.player_id = i
        if i > 1:
            player.name = f"Test Player {i}"
        else:
            player.name = "Test Player"
        player.model = "Test Model"
        player.version = "1.0.0"
        player.is_muted = False
        player.available = True
        player.state = const.PlayState.STOP
        player.ip_address = f"127.0.0.{i}"
        player.network = "wired"
        player.shuffle = False
        player.repeat = const.RepeatType.OFF
        player.volume = 25
        player.now_playing_media = Mock()
        player.now_playing_media.supported_controls = const.CONTROLS_ALL
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
        player.get_quick_selects.return_value = quick_selects
        players[player.player_id] = player
    return players


@pytest.fixture(name="group")
def group_fixture(players):
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
        type=const.MediaType.STATION,
        playable=True,
        browsable=False,
        image_url="",
        heos=None,
    )
    radio = MediaItem(
        source_id=const.MUSIC_SOURCE_TUNEIN,
        name="Classical MPR (Classical Music)",
        media_id="s1234",
        type=const.MediaType.STATION,
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
        type=const.MediaType.STATION,
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
        type=const.MediaType.PLAYLIST,
        playable=True,
        browsable=True,
        image_url="",
        heos=None,
    )
    return [playlist]


@pytest.fixture(name="change_data")
def change_data_fixture() -> dict:
    """Create player change data for testing."""
    return {const.DATA_MAPPED_IDS: {}, const.DATA_NEW: []}


@pytest.fixture(name="change_data_mapped_ids")
def change_data_mapped_ids_fixture() -> dict:
    """Create player change data for testing."""
    return {const.DATA_MAPPED_IDS: {101: 1}, const.DATA_NEW: []}

"""Configuration for HEOS tests."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import Mock, patch

from pyheos import (
    HeosGroup,
    HeosHost,
    HeosNowPlayingMedia,
    HeosOptions,
    HeosPlayer,
    HeosSystem,
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

from . import MockHeos

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


@pytest.fixture(name="new_mock", autouse=True)
def new_heos_mock_fixture(controller: MockHeos) -> Iterator[Mock]:
    """Patch the Heos class to return the mock instance."""
    new_mock = Mock(return_value=controller)
    with (
        patch("homeassistant.components.heos.coordinator.Heos", new=new_mock),
        patch("homeassistant.components.heos.config_flow.Heos", new=new_mock),
    ):
        yield new_mock


@pytest_asyncio.fixture(name="controller", autouse=True)
async def controller_fixture(
    players: dict[int, HeosPlayer],
    favorites: dict[int, MediaItem],
    input_sources: list[MediaItem],
    playlists: list[MediaItem],
    change_data: PlayerUpdateResult,
    group: dict[int, HeosGroup],
    quick_selects: dict[int, str],
) -> MockHeos:
    """Create a mock Heos controller fixture."""

    mock_heos = MockHeos(HeosOptions(host="127.0.0.1"))
    mock_heos.mock_set_signed_in_username("user@user.com")
    mock_heos.mock_set_players(players)
    mock_heos.mock_set_groups(group)
    mock_heos.get_favorites.return_value = favorites
    mock_heos.get_input_sources.return_value = input_sources
    mock_heos.get_playlists.return_value = playlists
    mock_heos.load_players.return_value = change_data
    mock_heos.player_get_quick_selects.return_value = quick_selects
    return mock_heos


@pytest.fixture(name="system")
def system_info_fixture() -> HeosSystem:
    """Create a system info fixture."""
    main_host = HeosHost(
        "Test Player",
        "HEOS Drive HS2",
        "123456",
        "1.0.0",
        "127.0.0.1",
        NetworkType.WIRED,
    )
    return HeosSystem(
        "user@user.com",
        main_host,
        hosts=[
            main_host,
            HeosHost(
                "Test Player 2",
                "Speaker",
                "123456",
                "1.0.0",
                "127.0.0.2",
                NetworkType.WIFI,
            ),
        ],
    )


@pytest.fixture(name="players")
def players_fixture() -> dict[int, HeosPlayer]:
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
        )
        player.now_playing_media = HeosNowPlayingMedia(
            type=MediaType.STATION,
            song="Song",
            station="Station Name",
            album="Album",
            artist="Artist",
            image_url="http://",
            album_id="1",
            media_id="1",
            queue_id=1,
            source_id=10,
        )
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

"""Configuration for Sonos tests."""

import asyncio
from collections.abc import Callable, Coroutine, Generator
from copy import copy
from ipaddress import ip_address
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from soco import SoCo
from soco.alarms import Alarms
from soco.data_structures import (
    DidlFavorite,
    DidlMusicTrack,
    DidlPlaylistContainer,
    SearchResult,
)
from soco.events_base import Event as SonosEvent

from homeassistant.components import ssdp
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.sonos import DOMAIN
from homeassistant.const import CONF_HOSTS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.ssdp import ATTR_UPNP_UDN, SsdpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture, load_json_value_fixture


class SonosMockEventListener:
    """Mock the event listener."""

    def __init__(self, ip_address: str) -> None:
        """Initialize the mock event listener."""
        self.address = [ip_address, "8080"]


class SonosMockSubscribe:
    """Mock the subscription."""

    def __init__(self, ip_address: str, *args, **kwargs) -> None:
        """Initialize the mock subscriber."""
        self.event_listener = SonosMockEventListener(ip_address)
        self.service = Mock()
        self.callback_future: asyncio.Future[Callable[[SonosEvent], None]] = None
        self._callback: Callable[[SonosEvent], None] | None = None

    @property
    def callback(self) -> Callable[[SonosEvent], None] | None:
        """Return the callback."""
        return self._callback

    @callback.setter
    def callback(self, callback: Callable[[SonosEvent], None]) -> None:
        """Set the callback."""
        self._callback = callback
        future = self._get_callback_future()
        if not future.done():
            future.set_result(callback)

    def _get_callback_future(self) -> asyncio.Future[Callable[[SonosEvent], None]]:
        """Get the callback future."""
        if not self.callback_future:
            self.callback_future = asyncio.get_running_loop().create_future()
        return self.callback_future

    async def wait_for_callback_to_be_set(self) -> Callable[[SonosEvent], None]:
        """Wait for the callback to be set."""
        return await self._get_callback_future()

    async def unsubscribe(self) -> None:
        """Unsubscribe mock."""


class SonosMockService:
    """Mock a Sonos Service used in callbacks."""

    def __init__(self, service_type, ip_address="192.168.42.2") -> None:
        """Initialize the instance."""
        self.service_type = service_type
        self.subscribe = AsyncMock(return_value=SonosMockSubscribe(ip_address))


class SonosMockEvent:
    """Mock a sonos Event used in callbacks."""

    def __init__(self, soco, service, variables) -> None:
        """Initialize the instance."""
        self.sid = f"{soco.uid}_sub0000000001"
        self.seq = "0"
        self.timestamp = 1621000000.0
        self.service = service
        self.variables = variables

    def increment_variable(self, var_name):
        """Increment the value of the var_name key in variables dict attribute.

        Assumes value has a format of <str>:<int>.
        """
        self.variables = copy(self.variables)
        base, count = self.variables[var_name].split(":")
        newcount = int(count) + 1
        self.variables[var_name] = ":".join([base, str(newcount)])
        return self.variables[var_name]


@pytest.fixture
def zeroconf_payload():
    """Return a default zeroconf payload."""
    return ZeroconfServiceInfo(
        ip_address=ip_address("192.168.4.2"),
        ip_addresses=[ip_address("192.168.4.2")],
        hostname="Sonos-aaa",
        name="Sonos-aaa@Living Room._sonos._tcp.local.",
        port=None,
        properties={"bootseq": "1234"},
        type="mock_type",
    )


@pytest.fixture
async def async_autosetup_sonos(async_setup_sonos):
    """Set up a Sonos integration instance on test run."""
    await async_setup_sonos()


@pytest.fixture
def async_setup_sonos(
    hass: HomeAssistant, config_entry: MockConfigEntry, fire_zgs_event
) -> Callable[[], Coroutine[Any, Any, None]]:
    """Return a coroutine to set up a Sonos integration instance on demand."""

    async def _wrapper():
        config_entry.add_to_hass(hass)
        sonos_alarms = Alarms()
        sonos_alarms.last_alarm_list_version = "RINCON_test:0"
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done(wait_background_tasks=True)
        await fire_zgs_event()
        await hass.async_block_till_done(wait_background_tasks=True)

    return _wrapper


@pytest.fixture(name="config_entry")
def config_entry_fixture() -> MockConfigEntry:
    """Create a mock Sonos config entry."""
    return MockConfigEntry(domain=DOMAIN, title="Sonos")


class MockSoCo(MagicMock):
    """Mock the Soco Object."""

    uid = "RINCON_test"
    play_mode = "NORMAL"
    mute = False
    night_mode = True
    dialog_level = True
    loudness = True
    volume = 19
    audio_delay = 2
    balance = (61, 100)
    bass = 1
    treble = -1
    mic_enabled = False
    sub_crossover = None  # Default to None for non-Amp devices
    sub_enabled = False
    sub_gain = 5
    surround_enabled = True
    surround_mode = True
    surround_level = 3
    music_surround_level = 4
    soundbar_audio_input_format = "Dolby 5.1"

    @property
    def visible_zones(self):
        """Return visible zones and allow property to be overridden by device classes."""
        return {self}


class SoCoMockFactory:
    """Factory for creating SoCo Mocks."""

    def __init__(
        self,
        music_library,
        speaker_info,
        current_track_info_empty,
        battery_info,
        alarm_clock,
        sonos_playlists: SearchResult,
        sonos_queue: list[DidlMusicTrack],
    ) -> None:
        """Initialize the mock factory."""
        self.mock_list: dict[str, MockSoCo] = {}
        self.music_library = music_library
        self.speaker_info = speaker_info
        self.current_track_info = current_track_info_empty
        self.battery_info = battery_info
        self.alarm_clock = alarm_clock
        self.sonos_playlists = sonos_playlists
        self.sonos_queue = sonos_queue

    def cache_mock(
        self, mock_soco: MockSoCo, ip_address: str, name: str = "Zone A"
    ) -> MockSoCo:
        """Put a user created mock into the cache."""
        mock_soco.mock_add_spec(SoCo)
        mock_soco.ip_address = ip_address
        if ip_address != "192.168.42.2":
            mock_soco.uid += f"_{ip_address}"
        mock_soco.music_library = self.music_library
        mock_soco.get_current_track_info.return_value = self.current_track_info
        mock_soco.music_source_from_uri = SoCo.music_source_from_uri
        mock_soco.get_sonos_playlists.return_value = self.sonos_playlists
        mock_soco.get_queue.return_value = self.sonos_queue
        my_speaker_info = self.speaker_info.copy()
        my_speaker_info["zone_name"] = name
        my_speaker_info["uid"] = mock_soco.uid
        mock_soco.get_speaker_info = Mock(return_value=my_speaker_info)
        mock_soco.add_to_queue = Mock(return_value=10)
        mock_soco.add_uri_to_queue = Mock(return_value=10)

        mock_soco.avTransport = SonosMockService("AVTransport", ip_address)
        mock_soco.renderingControl = SonosMockService("RenderingControl", ip_address)
        mock_soco.zoneGroupTopology = SonosMockService("ZoneGroupTopology", ip_address)
        mock_soco.contentDirectory = SonosMockService("ContentDirectory", ip_address)
        mock_soco.deviceProperties = SonosMockService("DeviceProperties", ip_address)
        mock_soco.alarmClock = self.alarm_clock
        mock_soco.get_battery_info.return_value = self.battery_info
        mock_soco.all_zones = {mock_soco}
        mock_soco.group.coordinator = mock_soco
        self.mock_list[ip_address] = mock_soco
        return mock_soco

    def get_mock(self, *args) -> SoCo:
        """Return a mock."""
        if len(args) > 0:
            ip_address = args[0]
        else:
            ip_address = "192.168.42.2"
        if ip_address in self.mock_list:
            return self.mock_list[ip_address]
        mock_soco = MockSoCo(name=f"Soco Mock {ip_address}")
        self.cache_mock(mock_soco, ip_address)
        return mock_soco


def patch_gethostbyname(host: str) -> str:
    """Mock to return host name as ip address for testing."""
    return host


@pytest.fixture(name="soco_sharelink")
def soco_sharelink():
    """Fixture to mock soco.plugins.sharelink.ShareLinkPlugin."""
    with patch("homeassistant.components.sonos.speaker.ShareLinkPlugin") as mock_share:
        mock_instance = MagicMock()
        mock_instance.is_share_link.return_value = True
        mock_instance.add_share_link_to_queue.return_value = 10
        mock_share.return_value = mock_instance
        yield mock_instance


@pytest.fixture(name="sonos_websocket")
def sonos_websocket():
    """Fixture to mock SonosWebSocket."""
    with patch(
        "homeassistant.components.sonos.speaker.SonosWebsocket"
    ) as mock_sonos_ws:
        mock_instance = AsyncMock()
        mock_instance.play_clip = AsyncMock()
        mock_instance.play_clip.return_value = [{"success": 1}, {}]
        mock_sonos_ws.return_value = mock_instance
        yield mock_instance


@pytest.fixture(name="soco_factory")
def soco_factory(
    music_library,
    speaker_info,
    current_track_info_empty,
    battery_info,
    alarm_clock,
    sonos_playlists: SearchResult,
    sonos_websocket,
    sonos_queue: list[DidlMusicTrack],
):
    """Create factory for instantiating SoCo mocks."""
    factory = SoCoMockFactory(
        music_library,
        speaker_info,
        current_track_info_empty,
        battery_info,
        alarm_clock,
        sonos_playlists,
        sonos_queue=sonos_queue,
    )
    with (
        patch("homeassistant.components.sonos.SoCo", new=factory.get_mock),
        patch("socket.gethostbyname", side_effect=patch_gethostbyname),
        patch("homeassistant.components.sonos.ZGS_SUBSCRIPTION_TIMEOUT", 0),
    ):
        yield factory


@pytest.fixture(name="soco")
def soco_fixture(soco_factory):
    """Create a default mock soco SoCo fixture."""
    return soco_factory.get_mock()


@pytest.fixture(autouse=True)
def silent_ssdp_scanner() -> Generator[None]:
    """Start SSDP component and get Scanner, prevent actual SSDP traffic."""
    with (
        patch("homeassistant.components.ssdp.Scanner._async_start_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner._async_stop_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner.async_scan"),
        patch(
            "homeassistant.components.ssdp.Server._async_start_upnp_servers",
        ),
        patch(
            "homeassistant.components.ssdp.Server._async_stop_upnp_servers",
        ),
    ):
        yield


@pytest.fixture(name="discover", autouse=True)
def discover_fixture(soco):
    """Create a mock soco discover fixture."""

    def do_callback(
        hass: HomeAssistant,
        callback: Callable[
            [SsdpServiceInfo, ssdp.SsdpChange], Coroutine[Any, Any, None] | None
        ],
        match_dict: dict[str, str] | None = None,
    ) -> MagicMock:
        callback(
            SsdpServiceInfo(
                ssdp_location=f"http://{soco.ip_address}/",
                ssdp_st="urn:schemas-upnp-org:device:ZonePlayer:1",
                ssdp_usn=f"uuid:{soco.uid}_MR::urn:schemas-upnp-org:service:GroupRenderingControl:1",
                upnp={
                    ATTR_UPNP_UDN: f"uuid:{soco.uid}",
                },
            ),
            ssdp.SsdpChange.ALIVE,
        )
        return MagicMock()

    with patch(
        "homeassistant.components.ssdp.async_register_callback", side_effect=do_callback
    ) as mock:
        yield mock


@pytest.fixture(name="config")
def config_fixture():
    """Create hass config fixture."""
    return {DOMAIN: {MP_DOMAIN: {CONF_HOSTS: ["192.168.42.2"]}}}


@pytest.fixture(name="sonos_favorites")
def sonos_favorites_fixture() -> SearchResult:
    """Create sonos favorites fixture."""
    favorites = load_json_value_fixture("sonos_favorites.json", "sonos")
    favorite_list = [DidlFavorite.from_dict(fav) for fav in favorites]
    return SearchResult(favorite_list, "favorites", 3, 3, 1)


@pytest.fixture(name="sonos_playlists")
def sonos_playlists_fixture() -> SearchResult:
    """Create sonos playlist fixture."""
    playlists = load_json_value_fixture("sonos_playlists.json", "sonos")
    playlists_list = [DidlPlaylistContainer.from_dict(pl) for pl in playlists]
    return SearchResult(playlists_list, "sonos_playlists", 1, 1, 0)


@pytest.fixture(name="sonos_queue")
def sonos_queue() -> list[DidlMusicTrack]:
    """Create sonos queue fixture."""
    queue = load_json_value_fixture("sonos_queue.json", "sonos")
    return [DidlMusicTrack.from_dict(track) for track in queue]


class MockMusicServiceItem:
    """Mocks a Soco MusicServiceItem."""

    def __init__(
        self,
        title: str,
        item_id: str,
        parent_id: str,
        item_class: str,
        album_art_uri: None | str = None,
    ) -> None:
        """Initialize the mock item."""
        self.title = title
        self.item_id = item_id
        self.item_class = item_class
        self.parent_id = parent_id
        self.album_art_uri: None | str = album_art_uri


def list_from_json_fixture(file_name: str) -> list[MockMusicServiceItem]:
    """Create a list of music service items from a json fixture file."""
    item_list = load_json_value_fixture(file_name, "sonos")
    return [
        MockMusicServiceItem(
            item.get("title"),
            item.get("item_id"),
            item.get("parent_id"),
            item.get("item_class"),
            item.get("album_art_uri"),
        )
        for item in item_list
    ]


def mock_browse_by_idstring(
    search_type: str, idstring: str, start=0, max_items=100, full_album_art_uri=False
) -> list[MockMusicServiceItem]:
    """Mock the call to browse_by_id_string."""
    if search_type == "album_artists" and idstring == "A:ALBUMARTIST/Beatles":
        return [
            MockMusicServiceItem(
                "All",
                idstring + "/",
                idstring,
                "object.container.playlistContainer.sameArtist",
            ),
            MockMusicServiceItem(
                "A Hard Day's Night",
                "A:ALBUMARTIST/Beatles/A%20Hard%20Day's%20Night",
                idstring,
                "object.container.album.musicAlbum",
            ),
            MockMusicServiceItem(
                "Abbey Road",
                "A:ALBUMARTIST/Beatles/Abbey%20Road",
                idstring,
                "object.container.album.musicAlbum",
            ),
        ]
    # browse_by_id_string works with URL encoded or decoded strings
    if search_type == "genres" and idstring in (
        "A:GENRE/Classic%20Rock",
        "A:GENRE/Classic Rock",
    ):
        return [
            MockMusicServiceItem(
                "All",
                "A:GENRE/Classic%20Rock/",
                "A:GENRE/Classic%20Rock",
                "object.container.albumlist",
            ),
            MockMusicServiceItem(
                "Bruce Springsteen",
                "A:GENRE/Classic%20Rock/Bruce%20Springsteen",
                "A:GENRE/Classic%20Rock",
                "object.container.person.musicArtist",
            ),
            MockMusicServiceItem(
                "Cream",
                "A:GENRE/Classic%20Rock/Cream",
                "A:GENRE/Classic%20Rock",
                "object.container.person.musicArtist",
            ),
        ]
    if search_type == "composers" and idstring in (
        "A:COMPOSER/Carlos%20Santana",
        "A:COMPOSER/Carlos Santana",
    ):
        return [
            MockMusicServiceItem(
                "All",
                "A:COMPOSER/Carlos%20Santana/",
                "A:COMPOSER/Carlos%20Santana",
                "object.container.playlistContainer.sameArtist",
            ),
            MockMusicServiceItem(
                "Between Good And Evil",
                "A:COMPOSER/Carlos%20Santana/Between%20Good%20And%20Evil",
                "A:COMPOSER/Carlos%20Santana",
                "object.container.album.musicAlbum",
            ),
            MockMusicServiceItem(
                "Sacred Fire",
                "A:COMPOSER/Carlos%20Santana/Sacred%20Fire",
                "A:COMPOSER/Carlos%20Santana",
                "object.container.album.musicAlbum",
            ),
        ]
    if search_type == "tracks":
        return list_from_json_fixture("music_library_tracks.json")
    if search_type == "albums" and idstring == "A:ALBUM":
        return list_from_json_fixture("music_library_albums.json")
    return []


def mock_get_music_library_information(
    search_type: str, search_term: str | None = None, full_album_art_uri: bool = True
) -> list[MockMusicServiceItem]:
    """Mock the call to get music library information."""
    if search_type == "albums" and search_term == "Abbey Road":
        return [
            MockMusicServiceItem(
                "Abbey Road",
                "A:ALBUM/Abbey%20Road",
                "A:ALBUM",
                "object.container.album.musicAlbum",
            )
        ]
    if search_type == "sonos_playlists":
        playlists = load_json_value_fixture("sonos_playlists.json", "sonos")
        playlists_list = [DidlPlaylistContainer.from_dict(pl) for pl in playlists]
        return SearchResult(playlists_list, "sonos_playlists", 1, 1, 0)
    return []


@pytest.fixture(name="music_library_browse_categories")
def music_library_browse_categories() -> list[MockMusicServiceItem]:
    """Create fixture for top-level music library categories."""
    return list_from_json_fixture("music_library_categories.json")


@pytest.fixture(name="music_library")
def music_library_fixture(
    sonos_favorites: SearchResult,
    music_library_browse_categories: list[MockMusicServiceItem],
) -> Mock:
    """Create music_library fixture."""
    music_library = MagicMock()
    music_library.get_sonos_favorites.return_value = sonos_favorites
    music_library.browse_by_idstring = Mock(side_effect=mock_browse_by_idstring)
    music_library.get_music_library_information = mock_get_music_library_information
    music_library.browse = Mock(return_value=music_library_browse_categories)
    return music_library


@pytest.fixture(name="alarm_clock")
def alarm_clock_fixture():
    """Create alarmClock fixture."""
    alarm_clock = SonosMockService("AlarmClock")
    # pylint: disable-next=attribute-defined-outside-init
    alarm_clock.ListAlarms = Mock()
    alarm_clock.ListAlarms.return_value = {
        "CurrentAlarmListVersion": "RINCON_test:14",
        "CurrentAlarmList": "<Alarms>"
        '<Alarm ID="14" StartTime="07:00:00" Duration="02:00:00" Recurrence="DAILY" '
        'Enabled="1" RoomUUID="RINCON_test" ProgramURI="x-rincon-buzzer:0" '
        'ProgramMetaData="" PlayMode="SHUFFLE_NOREPEAT" Volume="25" '
        'IncludeLinkedZones="0"/>'
        "</Alarms>",
    }
    return alarm_clock


@pytest.fixture(name="alarm_clock_extended")
def alarm_clock_fixture_extended():
    """Create alarmClock fixture."""
    alarm_clock = SonosMockService("AlarmClock")
    # pylint: disable-next=attribute-defined-outside-init
    alarm_clock.ListAlarms = Mock()
    alarm_clock.ListAlarms.return_value = {
        "CurrentAlarmListVersion": "RINCON_test:15",
        "CurrentAlarmList": "<Alarms>"
        '<Alarm ID="14" StartTime="07:00:00" Duration="02:00:00" Recurrence="DAILY" '
        'Enabled="1" RoomUUID="RINCON_test" ProgramURI="x-rincon-buzzer:0" '
        'ProgramMetaData="" PlayMode="SHUFFLE_NOREPEAT" Volume="25" '
        'IncludeLinkedZones="0"/>'
        '<Alarm ID="15" StartTime="07:00:00" Duration="02:00:00" '
        'Recurrence="DAILY" Enabled="1" RoomUUID="RINCON_test" '
        'ProgramURI="x-rincon-buzzer:0" ProgramMetaData="" PlayMode="SHUFFLE_NOREPEAT" '
        'Volume="25" IncludeLinkedZones="0"/>'
        "</Alarms>",
    }
    return alarm_clock


@pytest.fixture(name="speaker_model")
def speaker_model_fixture(request: pytest.FixtureRequest):
    """Create fixture for the speaker model."""
    return getattr(request, "param", "Model Name")


@pytest.fixture(name="speaker_info")
def speaker_info_fixture(speaker_model):
    """Create speaker_info fixture."""
    return {
        "zone_name": "Zone A",
        "uid": "RINCON_test",
        "model_name": speaker_model,
        "model_number": "S12",
        "hardware_version": "1.20.1.6-1.1",
        "software_version": "49.2-64250",
        "mac_address": "00-11-22-33-44-55",
        "display_version": "13.1",
    }


@pytest.fixture(name="current_track_info_empty")
def current_track_info_empty_fixture():
    """Create current_track_info_empty fixture."""
    return {
        "title": "",
        "artist": "",
        "album": "",
        "album_art": "",
        "position": "NOT_IMPLEMENTED",
        "playlist_position": "1",
        "duration": "NOT_IMPLEMENTED",
        "uri": "",
        "metadata": "NOT_IMPLEMENTED",
    }


@pytest.fixture(name="battery_info")
def battery_info_fixture():
    """Create battery_info fixture."""
    return {
        "Health": "GREEN",
        "Level": 100,
        "Temperature": "NORMAL",
        "PowerSource": "SONOS_CHARGING_RING",
    }


@pytest.fixture(name="device_properties_event")
def device_properties_event_fixture(soco):
    """Create device_properties_event fixture."""
    variables = {
        "zone_name": "Zone A",
        "mic_enabled": "1",
        "more_info": "BattChg:NOT_CHARGING,RawBattPct:100,BattPct:100,BattTmp:25",
    }
    return SonosMockEvent(soco, soco.deviceProperties, variables)


@pytest.fixture(name="alarm_event")
def alarm_event_fixture(soco):
    """Create alarm_event fixture."""
    variables = {
        "time_zone": "ffc40a000503000003000502ffc4",
        "time_server": "0.sonostime.pool.ntp.org,1.sonostime.pool.ntp.org,2.sonostime.pool.ntp.org,3.sonostime.pool.ntp.org",
        "time_generation": "20000001",
        "alarm_list_version": "RINCON_test:1",
        "time_format": "INV",
        "date_format": "INV",
        "daily_index_refresh_time": None,
    }

    return SonosMockEvent(soco, soco.alarmClock, variables)


@pytest.fixture(name="no_media_event")
def no_media_event_fixture(soco):
    """Create no_media_event_fixture."""
    variables = {
        "current_crossfade_mode": "0",
        "current_play_mode": "NORMAL",
        "current_section": "0",
        "current_track_meta_data": "",
        "current_track_uri": "",
        "enqueued_transport_uri": "",
        "enqueued_transport_uri_meta_data": "",
        "number_of_tracks": "0",
        "transport_state": "STOPPED",
    }
    return SonosMockEvent(soco, soco.avTransport, variables)


@pytest.fixture(name="tv_event")
def tv_event_fixture(soco):
    """Create alarm_event fixture."""
    variables = {
        "transport_state": "PLAYING",
        "current_play_mode": "NORMAL",
        "current_crossfade_mode": "0",
        "number_of_tracks": "1",
        "current_track": "1",
        "current_section": "0",
        "current_track_uri": f"x-sonos-htastream:{soco.uid}:spdif",
        "current_track_duration": "",
        "current_track_meta_data": {
            "title": " ",
            "parent_id": "-1",
            "item_id": "-1",
            "restricted": True,
            "resources": [],
            "desc": None,
        },
        "next_track_uri": "",
        "next_track_meta_data": "",
        "enqueued_transport_uri": "",
        "enqueued_transport_uri_meta_data": "",
        "playback_storage_medium": "NETWORK",
        "av_transport_uri": f"x-sonos-htastream:{soco.uid}:spdif",
        "av_transport_uri_meta_data": {
            "title": soco.uid,
            "parent_id": "0",
            "item_id": "spdif-input",
            "restricted": False,
            "resources": [],
            "desc": None,
        },
        "current_transport_actions": "Set, Play",
        "current_valid_play_modes": "",
    }
    return SonosMockEvent(soco, soco.avTransport, variables)


@pytest.fixture(name="zgs_discovery", scope="package")
def zgs_discovery_fixture():
    """Load ZoneGroupState discovery payload and return it."""
    return load_fixture("sonos/zgs_discovery.xml")


@pytest.fixture(name="fire_zgs_event")
def zgs_event_fixture(
    hass: HomeAssistant, soco: SoCo, zgs_discovery: str
) -> Callable[[], Coroutine[Any, Any, None]]:
    """Create alarm_event fixture."""
    variables = {"ZoneGroupState": zgs_discovery}

    async def _wrapper():
        event = SonosMockEvent(soco, soco.zoneGroupTopology, variables)
        subscription: SonosMockSubscribe = soco.zoneGroupTopology.subscribe.return_value
        sub_callback = await subscription.wait_for_callback_to_be_set()
        sub_callback(event)
        await hass.async_block_till_done(wait_background_tasks=True)

    return _wrapper


@pytest.fixture(name="sonos_setup_two_speakers")
async def sonos_setup_two_speakers(
    hass: HomeAssistant, soco_factory: SoCoMockFactory
) -> list[MockSoCo]:
    """Set up home assistant with two Sonos Speakers."""
    soco_lr = soco_factory.cache_mock(MockSoCo(), "10.10.10.1", "Living Room")
    soco_br = soco_factory.cache_mock(MockSoCo(), "10.10.10.2", "Bedroom")
    await async_setup_component(
        hass,
        DOMAIN,
        {
            DOMAIN: {
                "media_player": {
                    "interface_addr": "127.0.0.1",
                    "hosts": ["10.10.10.1", "10.10.10.2"],
                }
            }
        },
    )
    await hass.async_block_till_done()
    return [soco_lr, soco_br]

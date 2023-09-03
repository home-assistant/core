"""Configuration for Sonos tests."""
from copy import copy
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from soco import SoCo

from homeassistant.components import ssdp, zeroconf
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.sonos import DOMAIN
from homeassistant.const import CONF_HOSTS

from tests.common import MockConfigEntry, load_fixture


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

    def __init__(self, soco, service, variables):
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
    return zeroconf.ZeroconfServiceInfo(
        host="192.168.4.2",
        addresses=["192.168.4.2"],
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
def async_setup_sonos(hass, config_entry, fire_zgs_event):
    """Return a coroutine to set up a Sonos integration instance on demand."""

    async def _wrapper():
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        await fire_zgs_event()

    return _wrapper


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create a mock Sonos config entry."""
    return MockConfigEntry(domain=DOMAIN, title="Sonos")


class MockSoCo(MagicMock):
    """Mock the Soco Object."""

    audio_delay = 2
    sub_gain = 5

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
    ) -> None:
        """Initialize the mock factory."""
        self.mock_list: dict[str, MockSoCo] = {}
        self.music_library = music_library
        self.speaker_info = speaker_info
        self.current_track_info = current_track_info_empty
        self.battery_info = battery_info
        self.alarm_clock = alarm_clock

    def cache_mock(
        self, mock_soco: MockSoCo, ip_address: str, name: str = "Zone A"
    ) -> MockSoCo:
        """Put a user created mock into the cache."""
        mock_soco.mock_add_spec(SoCo)
        mock_soco.ip_address = ip_address
        if ip_address != "192.168.42.2":
            mock_soco.uid = f"RINCON_test_{ip_address}"
        else:
            mock_soco.uid = "RINCON_test"
        mock_soco.play_mode = "NORMAL"
        mock_soco.music_library = self.music_library
        mock_soco.get_current_track_info.return_value = self.current_track_info
        mock_soco.music_source_from_uri = SoCo.music_source_from_uri
        my_speaker_info = self.speaker_info.copy()
        my_speaker_info["zone_name"] = name
        my_speaker_info["uid"] = mock_soco.uid
        mock_soco.get_speaker_info = Mock(return_value=my_speaker_info)

        mock_soco.avTransport = SonosMockService("AVTransport", ip_address)
        mock_soco.renderingControl = SonosMockService("RenderingControl", ip_address)
        mock_soco.zoneGroupTopology = SonosMockService("ZoneGroupTopology", ip_address)
        mock_soco.contentDirectory = SonosMockService("ContentDirectory", ip_address)
        mock_soco.deviceProperties = SonosMockService("DeviceProperties", ip_address)
        mock_soco.alarmClock = self.alarm_clock
        mock_soco.mute = False
        mock_soco.night_mode = True
        mock_soco.dialog_level = True
        mock_soco.loudness = True
        mock_soco.volume = 19
        mock_soco.audio_delay = 2
        mock_soco.balance = (61, 100)
        mock_soco.bass = 1
        mock_soco.treble = -1
        mock_soco.mic_enabled = False
        mock_soco.sub_enabled = False
        mock_soco.sub_gain = 5
        mock_soco.surround_enabled = True
        mock_soco.surround_mode = True
        mock_soco.surround_level = 3
        mock_soco.music_surround_level = 4
        mock_soco.soundbar_audio_input_format = "Dolby 5.1"
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


@pytest.fixture(name="soco_factory")
def soco_factory(
    music_library, speaker_info, current_track_info_empty, battery_info, alarm_clock
):
    """Create factory for instantiating SoCo mocks."""
    factory = SoCoMockFactory(
        music_library, speaker_info, current_track_info_empty, battery_info, alarm_clock
    )
    with patch("homeassistant.components.sonos.SoCo", new=factory.get_mock), patch(
        "socket.gethostbyname", side_effect=patch_gethostbyname
    ), patch("homeassistant.components.sonos.ZGS_SUBSCRIPTION_TIMEOUT", 0):
        yield factory


@pytest.fixture(name="soco")
def soco_fixture(soco_factory):
    """Create a default mock soco SoCo fixture."""
    return soco_factory.get_mock()


@pytest.fixture(autouse=True)
async def silent_ssdp_scanner(hass):
    """Start SSDP component and get Scanner, prevent actual SSDP traffic."""
    with patch(
        "homeassistant.components.ssdp.Scanner._async_start_ssdp_listeners"
    ), patch("homeassistant.components.ssdp.Scanner._async_stop_ssdp_listeners"), patch(
        "homeassistant.components.ssdp.Scanner.async_scan"
    ), patch(
        "homeassistant.components.ssdp.Server._async_start_upnp_servers"
    ), patch(
        "homeassistant.components.ssdp.Server._async_stop_upnp_servers"
    ):
        yield


@pytest.fixture(name="discover", autouse=True)
def discover_fixture(soco):
    """Create a mock soco discover fixture."""

    async def do_callback(hass, callback, *args, **kwargs):
        await callback(
            ssdp.SsdpServiceInfo(
                ssdp_location=f"http://{soco.ip_address}/",
                ssdp_st="urn:schemas-upnp-org:device:ZonePlayer:1",
                ssdp_usn=f"uuid:{soco.uid}_MR::urn:schemas-upnp-org:service:GroupRenderingControl:1",
                upnp={
                    ssdp.ATTR_UPNP_UDN: f"uuid:{soco.uid}",
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


@pytest.fixture(name="music_library")
def music_library_fixture():
    """Create music_library fixture."""
    music_library = MagicMock()
    music_library.get_sonos_favorites.return_value.update_id = 1
    return music_library


@pytest.fixture(name="alarm_clock")
def alarm_clock_fixture():
    """Create alarmClock fixture."""
    alarm_clock = SonosMockService("AlarmClock")
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


@pytest.fixture(name="speaker_info")
def speaker_info_fixture():
    """Create speaker_info fixture."""
    return {
        "zone_name": "Zone A",
        "uid": "RINCON_test",
        "model_name": "Model Name",
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


@pytest.fixture(autouse=True)
def mock_get_source_ip(mock_get_source_ip):
    """Mock network util's async_get_source_ip in all sonos tests."""
    return mock_get_source_ip


@pytest.fixture(name="zgs_discovery", scope="session")
def zgs_discovery_fixture():
    """Load ZoneGroupState discovery payload and return it."""
    return load_fixture("sonos/zgs_discovery.xml")


@pytest.fixture(name="fire_zgs_event")
def zgs_event_fixture(hass, soco, zgs_discovery):
    """Create alarm_event fixture."""
    variables = {"ZoneGroupState": zgs_discovery}

    async def _wrapper():
        event = SonosMockEvent(soco, soco.zoneGroupTopology, variables)
        subscription = soco.zoneGroupTopology.subscribe.return_value
        sub_callback = subscription.callback
        sub_callback(event)
        await hass.async_block_till_done()

    return _wrapper

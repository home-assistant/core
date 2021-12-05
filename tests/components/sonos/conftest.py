"""Configuration for Sonos tests."""
from unittest.mock import AsyncMock, MagicMock, Mock, patch as patch

import pytest

from homeassistant.components import ssdp
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.components.sonos import DOMAIN
from homeassistant.const import CONF_HOSTS

from tests.common import MockConfigEntry


class SonosMockService:
    """Mock a Sonos Service used in callbacks."""

    def __init__(self, service_type):
        """Initialize the instance."""
        self.service_type = service_type
        self.subscribe = AsyncMock()


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
        base, count = self.variables[var_name].split(":")
        newcount = int(count) + 1
        self.variables[var_name] = ":".join([base, str(newcount)])
        return self.variables[var_name]


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create a mock Sonos config entry."""
    return MockConfigEntry(domain=DOMAIN, title="Sonos")


@pytest.fixture(name="soco")
def soco_fixture(music_library, speaker_info, battery_info, alarm_clock):
    """Create a mock soco SoCo fixture."""
    with patch("homeassistant.components.sonos.SoCo", autospec=True) as mock, patch(
        "socket.gethostbyname", return_value="192.168.42.2"
    ):
        mock_soco = mock.return_value
        mock_soco.ip_address = "192.168.42.2"
        mock_soco.uid = "RINCON_test"
        mock_soco.play_mode = "NORMAL"
        mock_soco.music_library = music_library
        mock_soco.get_speaker_info.return_value = speaker_info
        mock_soco.avTransport = SonosMockService("AVTransport")
        mock_soco.renderingControl = SonosMockService("RenderingControl")
        mock_soco.zoneGroupTopology = SonosMockService("ZoneGroupTopology")
        mock_soco.contentDirectory = SonosMockService("ContentDirectory")
        mock_soco.deviceProperties = SonosMockService("DeviceProperties")
        mock_soco.alarmClock = alarm_clock
        mock_soco.mute = False
        mock_soco.night_mode = True
        mock_soco.dialog_mode = True
        mock_soco.volume = 19
        mock_soco.get_battery_info.return_value = battery_info
        mock_soco.all_zones = [mock_soco]
        yield mock_soco


@pytest.fixture(autouse=True)
async def silent_ssdp_scanner(hass):
    """Start SSDP component and get Scanner, prevent actual SSDP traffic."""
    with patch(
        "homeassistant.components.ssdp.Scanner._async_start_ssdp_listeners"
    ), patch("homeassistant.components.ssdp.Scanner._async_stop_ssdp_listeners"), patch(
        "homeassistant.components.ssdp.Scanner.async_scan"
    ):
        yield


@pytest.fixture(name="discover", autouse=True)
def discover_fixture(soco):
    """Create a mock soco discover fixture."""

    async def do_callback(hass, callback, *args, **kwargs):
        await callback(
            {
                ssdp.ATTR_UPNP_UDN: f"uuid:{soco.uid}",
                ssdp.ATTR_SSDP_LOCATION: f"http://{soco.ip_address}/",
            },
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
    return {DOMAIN: {MP_DOMAIN: {CONF_HOSTS: ["192.168.42.1"]}}}


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
        "software_version": "49.2-64250",
        "mac_address": "00-11-22-33-44-55",
        "display_version": "13.1",
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


@pytest.fixture(name="battery_event")
def battery_event_fixture(soco):
    """Create battery_event fixture."""
    variables = {
        "zone_name": "Zone A",
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


@pytest.fixture(autouse=True)
def mock_get_source_ip(mock_get_source_ip):
    """Mock network util's async_get_source_ip in all sonos tests."""
    return mock_get_source_ip

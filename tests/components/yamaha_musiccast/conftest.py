"""Fixtures for the MusicCast integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aiomusiccast.capabilities import BinarySetter, EntityType
from aiomusiccast.features import DeviceFeature, ZoneFeature
from aiomusiccast.musiccast_data import (
    Dimmer,
    MusicCastAlarmDetails,
    MusicCastData,
    MusicCastZoneData,
    RangeStep,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.yamaha_musiccast.const import DEFAULT_ZONE, DOMAIN
from homeassistant.const import CONF_HOST

TEST_DEVICE_ID = "1234567890"
TEST_ZONE = "zone2"


@pytest.fixture(autouse=True)
def silent_ssdp_scanner() -> Generator[None]:
    """Start SSDP component and get Scanner, prevent actual SSDP traffic."""
    with (
        patch("homeassistant.components.ssdp.Scanner._async_start_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner._async_stop_ssdp_listeners"),
        patch("homeassistant.components.ssdp.Scanner.async_scan"),
        patch("homeassistant.components.ssdp.Server._async_start_upnp_servers"),
        patch("homeassistant.components.ssdp.Server._async_stop_upnp_servers"),
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a MusicCast config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_DEVICE_ID,
        data={
            CONF_HOST: "127.0.0.1",
            "serial": TEST_DEVICE_ID,
            "upnp_description": "http://127.0.0.1:49154/MediaRenderer/desc.xml",
        },
    )


@pytest.fixture
def mock_musiccast_device() -> Generator[MagicMock]:
    """Mock a MusicCast device with a main zone and a sub-zone."""
    data = MusicCastData()
    data.device_id = TEST_DEVICE_ID
    data.model_name = "MC20"
    data.system_version = "1.0"
    data.api_version = "2.11"
    data.mac_addresses = {"main": "001122334455"}
    data.network_name = "MusicCast"
    data.input_names = {"net_radio": "NET RADIO", "bluetooth": "Bluetooth"}
    data.sound_program_names = {"music": "Music", "movie": "Movie"}
    data.netusb_input = "net_radio"
    data.netusb_playback = "play"
    data.netusb_repeat = "off"
    data.netusb_shuffle = "off"
    data.netusb_artist = "Artist"
    data.netusb_track = "Track"
    data.dimmer = Dimmer(-1, 15, 1, 5)
    data.party_enable = False
    data.alarm_details = {
        "oneday": MusicCastAlarmDetails(
            enabled=True,
            time="0700",
            playback_type="preset",
            preset=1,
            preset_type="netusb",
            preset_info={"input": "net_radio", "text": "My Station"},
            beep=False,
        )
    }

    main_zone = MusicCastZoneData()
    main_zone.name = "Main"
    main_zone.power = True
    main_zone.current_volume = 30
    main_zone.max_volume = 60
    main_zone.input_list = ["net_radio", "bluetooth"]
    main_zone.input = "net_radio"
    main_zone.sound_program_list = ["music", "movie"]
    main_zone.sound_program = "music"
    main_zone.func_list = ["power", "volume", "mute", "sound_program"]
    main_zone.features = (
        ZoneFeature.POWER
        | ZoneFeature.VOLUME
        | ZoneFeature.MUTE
        | ZoneFeature.SOUND_PROGRAM
    )
    main_zone.range_step = {"volume": RangeStep(0, 60, 1)}
    sub_zone = MusicCastZoneData()
    sub_zone.name = "Zone 2"
    # A capability on the sub-zone makes the switch platform register the
    # sub-zone device, which links back to the main device via via_device_id.
    sub_zone.capabilities = [
        BinarySetter("power", "Power", EntityType.CONFIG, lambda: False, AsyncMock())
    ]
    data.zones = {DEFAULT_ZONE: main_zone, TEST_ZONE: sub_zone}

    device = MagicMock()
    device.data = data
    device.ip = "127.0.0.1"
    device.features = DeviceFeature.WIRED_LAN | DeviceFeature.PARTY_MODE
    device.fetch = AsyncMock()
    device.build_capabilities = MagicMock()
    device.device = MagicMock()
    device.device.enable_polling = AsyncMock()

    with patch(
        "homeassistant.components.yamaha_musiccast.MusicCastDevice",
        return_value=device,
    ):
        yield device

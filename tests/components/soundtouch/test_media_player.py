"""Test the Soundtouch component."""
from unittest.mock import call

from asynctest import patch
from libsoundtouch.device import (
    Config,
    Preset,
    SoundTouchDevice as STD,
    Status,
    Volume,
    ZoneSlave,
    ZoneStatus,
)
import pytest

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
)
from homeassistant.components.soundtouch import media_player as soundtouch
from homeassistant.components.soundtouch.const import DOMAIN
from homeassistant.components.soundtouch.media_player import (
    ATTR_SOUNDTOUCH_GROUP,
    ATTR_SOUNDTOUCH_ZONE,
    DATA_SOUNDTOUCH,
)
from homeassistant.const import STATE_OFF, STATE_PAUSED, STATE_PLAYING
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.setup import async_setup_component

# pylint: disable=super-init-not-called


DEVICE_1_IP = "192.168.0.1"
DEVICE_2_IP = "192.168.0.2"
DEVICE_1_ID = 1
DEVICE_2_ID = 2


def get_config(host=DEVICE_1_IP, port=8090, name="soundtouch"):
    """Return a default component."""
    return {"platform": DOMAIN, "host": host, "port": port, "name": name}


DEVICE_1_CONFIG = {**get_config(), "name": "soundtouch_1"}
DEVICE_2_CONFIG = {**get_config(), "host": DEVICE_2_IP, "name": "soundtouch_2"}


@pytest.fixture(name="one_device")
def one_device_fixture():
    """Mock one master device."""
    device_1 = MockDevice()
    device_patch = patch(
        "homeassistant.components.soundtouch.media_player.soundtouch_device",
        return_value=device_1,
    )
    with device_patch as device:
        yield device


@pytest.fixture(name="two_zones")
def two_zones_fixture():
    """Mock one master and one slave."""
    device_1 = MockDevice(
        DEVICE_1_ID,
        MockZoneStatus(
            is_master=True,
            master_id=DEVICE_1_ID,
            master_ip=DEVICE_1_IP,
            slaves=[MockZoneSlave(DEVICE_2_IP)],
        ),
    )
    device_2 = MockDevice(
        DEVICE_2_ID,
        MockZoneStatus(
            is_master=False,
            master_id=DEVICE_1_ID,
            master_ip=DEVICE_1_IP,
            slaves=[MockZoneSlave(DEVICE_2_IP)],
        ),
    )
    devices = {DEVICE_1_IP: device_1, DEVICE_2_IP: device_2}
    device_patch = patch(
        "homeassistant.components.soundtouch.media_player.soundtouch_device",
        side_effect=lambda host, _: devices[host],
    )
    with device_patch as device:
        yield device


@pytest.fixture(name="mocked_status")
def status_fixture():
    """Mock the device status."""
    status_patch = patch(
        "libsoundtouch.device.SoundTouchDevice.status", side_effect=MockStatusPlaying
    )
    with status_patch as status:
        yield status


@pytest.fixture(name="mocked_volume")
def volume_fixture():
    """Mock the device volume."""
    volume_patch = patch("libsoundtouch.device.SoundTouchDevice.volume")
    with volume_patch as volume:
        yield volume


async def setup_soundtouch(hass, config):
    """Set up soundtouch integration."""
    assert await async_setup_component(hass, "media_player", {"media_player": config})
    await hass.async_block_till_done()
    await hass.async_start()


class MockDevice(STD):
    """Mock device."""

    def __init__(self, id=None, zone_status=None):
        """Init the class."""
        self._config = MockConfig(id)
        self._zone_status = zone_status or MockZoneStatus()

    def zone_status(self, refresh=True):
        """Zone status mock object."""
        return self._zone_status


class MockConfig(Config):
    """Mock config."""

    def __init__(self, id=None):
        """Init class."""
        self._name = "name"
        self._id = id or DEVICE_1_ID


class MockZoneStatus(ZoneStatus):
    """Mock zone status."""

    def __init__(self, is_master=True, master_id=None, master_ip=None, slaves=None):
        """Init the class."""
        self._is_master = is_master
        self._master_id = master_id
        self._master_ip = master_ip
        self._slaves = slaves or []


class MockZoneSlave(ZoneSlave):
    """Mock zone slave."""

    def __init__(self, device_ip=None, role=None):
        """Init the class."""
        self._ip = device_ip
        self._role = role


def _mocked_presets(*args, **kwargs):
    """Return a list of mocked presets."""
    return [MockPreset("1")]


class MockPreset(Preset):
    """Mock preset."""

    def __init__(self, id_):
        """Init the class."""
        self._id = id_
        self._name = "preset"


class MockVolume(Volume):
    """Mock volume with value."""

    def __init__(self):
        """Init class."""
        self._actual = 12
        self._muted = False


class MockVolumeMuted(Volume):
    """Mock volume muted."""

    def __init__(self):
        """Init the class."""
        self._actual = 12
        self._muted = True


class MockStatusStandby(Status):
    """Mock status standby."""

    def __init__(self):
        """Init the class."""
        self._source = "STANDBY"


class MockStatusPlaying(Status):
    """Mock status playing media."""

    def __init__(self):
        """Init the class."""
        self._source = ""
        self._play_status = "PLAY_STATE"
        self._image = "image.url"
        self._artist = "artist"
        self._track = "track"
        self._album = "album"
        self._duration = 1
        self._station_name = None


class MockStatusPlayingRadio(Status):
    """Mock status radio."""

    def __init__(self):
        """Init the class."""
        self._source = ""
        self._play_status = "PLAY_STATE"
        self._image = "image.url"
        self._artist = None
        self._track = None
        self._album = None
        self._duration = None
        self._station_name = "station"


class MockStatusUnknown(Status):
    """Mock status unknown media."""

    def __init__(self):
        """Init the class."""
        self._source = ""
        self._play_status = "PLAY_STATE"
        self._image = "image.url"
        self._artist = None
        self._track = None
        self._album = None
        self._duration = None
        self._station_name = None


class MockStatusPause(Status):
    """Mock status pause."""

    def __init__(self):
        """Init the class."""
        self._source = ""
        self._play_status = "PAUSE_STATE"
        self._image = "image.url"
        self._artist = None
        self._track = None
        self._album = None
        self._duration = None
        self._station_name = None


async def test_ensure_setup_config(mocked_status, mocked_volume, hass, one_device):
    """Test setup OK with custom config."""
    await setup_soundtouch(
        hass, get_config(host="192.168.1.44", port=8888, name="custom_sound")
    )

    assert one_device.call_count == 1
    assert one_device.call_args == call("192.168.1.44", 8888)
    assert len(hass.states.async_all()) == 1
    state = hass.states.get("media_player.custom_sound")
    assert state.name == "custom_sound"


async def test_ensure_setup_discovery(mocked_status, mocked_volume, hass, one_device):
    """Test setup with discovery."""
    new_device = {
        "port": "8090",
        "host": "192.168.1.1",
        "properties": {},
        "hostname": "hostname.local",
    }
    await async_load_platform(
        hass, "media_player", DOMAIN, new_device, {"media_player": {}}
    )
    await hass.async_block_till_done()

    assert one_device.call_count == 1
    assert one_device.call_args == call("192.168.1.1", 8090)
    assert len(hass.states.async_all()) == 1


async def test_ensure_setup_discovery_no_duplicate(
    mocked_status, mocked_volume, hass, one_device
):
    """Test setup OK if device already exists."""
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert len(hass.states.async_all()) == 1

    new_device = {
        "port": "8090",
        "host": "192.168.1.1",
        "properties": {},
        "hostname": "hostname.local",
    }
    await async_load_platform(
        hass, "media_player", DOMAIN, new_device, {"media_player": DEVICE_1_CONFIG}
    )
    await hass.async_block_till_done()
    assert one_device.call_count == 2
    assert len(hass.states.async_all()) == 2

    existing_device = {
        "port": "8090",
        "host": "192.168.0.1",
        "properties": {},
        "hostname": "hostname.local",
    }
    await async_load_platform(
        hass, "media_player", DOMAIN, existing_device, {"media_player": DEVICE_1_CONFIG}
    )
    await hass.async_block_till_done()
    assert one_device.call_count == 2
    assert len(hass.states.async_all()) == 2


async def test_playing_media(mocked_status, mocked_volume, hass, one_device):
    """Test playing media info."""
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    entity_1_state = hass.states.get("media_player.soundtouch_1")
    assert entity_1_state.state == STATE_PLAYING
    assert entity_1_state.attributes["media_title"] == "artist - track"
    assert entity_1_state.attributes["media_track"] == "track"
    assert entity_1_state.attributes["media_artist"] == "artist"
    assert entity_1_state.attributes["media_album_name"] == "album"
    assert entity_1_state.attributes["media_duration"] == 1


async def test_playing_unknown_media(mocked_status, mocked_volume, hass, one_device):
    """Test playing media info."""
    mocked_status.side_effect = MockStatusUnknown
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    entity_1_state = hass.states.get("media_player.soundtouch_1")
    assert entity_1_state.state == STATE_PLAYING


async def test_playing_radio(mocked_status, mocked_volume, hass, one_device):
    """Test playing radio info."""
    mocked_status.side_effect = MockStatusPlayingRadio
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    entity_1_state = hass.states.get("media_player.soundtouch_1")
    assert entity_1_state.state == STATE_PLAYING
    assert entity_1_state.attributes["media_title"] == "station"


async def test_get_volume_level(mocked_status, mocked_volume, hass, one_device):
    """Test volume level."""
    mocked_volume.side_effect = MockVolume
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    entity_1_state = hass.states.get("media_player.soundtouch_1")
    assert entity_1_state.attributes["volume_level"] == 0.12


async def test_get_state_off(mocked_status, mocked_volume, hass, one_device):
    """Test state device is off."""
    mocked_status.side_effect = MockStatusStandby
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    entity_1_state = hass.states.get("media_player.soundtouch_1")
    assert entity_1_state.state == STATE_OFF


async def test_get_state_pause(mocked_status, mocked_volume, hass, one_device):
    """Test state device is paused."""
    mocked_status.side_effect = MockStatusPause
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    entity_1_state = hass.states.get("media_player.soundtouch_1")
    assert entity_1_state.state == STATE_PAUSED


async def test_is_muted(mocked_status, mocked_volume, hass, one_device):
    """Test device volume is muted."""
    mocked_volume.side_effect = MockVolumeMuted
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    entity_1_state = hass.states.get("media_player.soundtouch_1")
    assert entity_1_state.attributes["is_volume_muted"]


async def test_media_commands(mocked_status, mocked_volume, hass, one_device):
    """Test supported media commands."""
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    entity_1_state = hass.states.get("media_player.soundtouch_1")
    assert entity_1_state.attributes["supported_features"] == 18365


@patch("libsoundtouch.device.SoundTouchDevice.power_off")
async def test_should_turn_off(
    mocked_power_off, mocked_status, mocked_volume, hass, one_device
):
    """Test device is turned off."""
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    await hass.services.async_call(
        "media_player", "turn_off", {"entity_id": "media_player.soundtouch_1"}, True,
    )
    assert mocked_status.call_count == 3
    assert mocked_power_off.call_count == 1


@patch("libsoundtouch.device.SoundTouchDevice.power_on")
async def test_should_turn_on(
    mocked_power_on, mocked_status, mocked_volume, hass, one_device
):
    """Test device is turned on."""
    mocked_status.side_effect = MockStatusStandby
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    await hass.services.async_call(
        "media_player", "turn_on", {"entity_id": "media_player.soundtouch_1"}, True,
    )
    assert mocked_status.call_count == 3
    assert mocked_power_on.call_count == 1


@patch("libsoundtouch.device.SoundTouchDevice.volume_up")
async def test_volume_up(
    mocked_volume_up, mocked_status, mocked_volume, hass, one_device
):
    """Test volume up."""
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    await hass.services.async_call(
        "media_player", "volume_up", {"entity_id": "media_player.soundtouch_1"}, True,
    )
    assert mocked_volume.call_count == 3
    assert mocked_volume_up.call_count == 1


@patch("libsoundtouch.device.SoundTouchDevice.volume_down")
async def test_volume_down(
    mocked_volume_down, mocked_status, mocked_volume, hass, one_device
):
    """Test volume down."""
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    await hass.services.async_call(
        "media_player", "volume_down", {"entity_id": "media_player.soundtouch_1"}, True,
    )
    assert mocked_volume.call_count == 3
    assert mocked_volume_down.call_count == 1


@patch("libsoundtouch.device.SoundTouchDevice.set_volume")
async def test_set_volume_level(
    mocked_set_volume, mocked_status, mocked_volume, hass, one_device
):
    """Test set volume level."""
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    await hass.services.async_call(
        "media_player",
        "volume_set",
        {"entity_id": "media_player.soundtouch_1", "volume_level": 0.17},
        True,
    )
    assert mocked_volume.call_count == 3
    mocked_set_volume.assert_called_with(17)


@patch("libsoundtouch.device.SoundTouchDevice.mute")
async def test_mute(mocked_mute, mocked_status, mocked_volume, hass, one_device):
    """Test mute volume."""
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    await hass.services.async_call(
        "media_player",
        "volume_mute",
        {"entity_id": "media_player.soundtouch_1", "is_volume_muted": True},
        True,
    )
    assert mocked_volume.call_count == 3
    assert mocked_mute.call_count == 1


@patch("libsoundtouch.device.SoundTouchDevice.play")
async def test_play(mocked_play, mocked_status, mocked_volume, hass, one_device):
    """Test play command."""
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    await hass.services.async_call(
        "media_player", "media_play", {"entity_id": "media_player.soundtouch_1"}, True,
    )
    assert mocked_status.call_count == 3
    assert mocked_play.call_count == 1


@patch("libsoundtouch.device.SoundTouchDevice.pause")
async def test_pause(mocked_pause, mocked_status, mocked_volume, hass, one_device):
    """Test pause command."""
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    await hass.services.async_call(
        "media_player", "media_pause", {"entity_id": "media_player.soundtouch_1"}, True,
    )
    assert mocked_status.call_count == 3
    assert mocked_pause.call_count == 1


@patch("libsoundtouch.device.SoundTouchDevice.play_pause")
async def test_play_pause(
    mocked_play_pause, mocked_status, mocked_volume, hass, one_device
):
    """Test play/pause."""
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    await hass.services.async_call(
        "media_player",
        "media_play_pause",
        {"entity_id": "media_player.soundtouch_1"},
        True,
    )
    assert mocked_status.call_count == 3
    assert mocked_play_pause.call_count == 1


@patch("libsoundtouch.device.SoundTouchDevice.previous_track")
@patch("libsoundtouch.device.SoundTouchDevice.next_track")
async def test_next_previous_track(
    mocked_next_track,
    mocked_previous_track,
    mocked_status,
    mocked_volume,
    hass,
    one_device,
):
    """Test next/previous track."""
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    await hass.services.async_call(
        "media_player",
        "media_next_track",
        {"entity_id": "media_player.soundtouch_1"},
        True,
    )
    assert mocked_status.call_count == 3
    assert mocked_next_track.call_count == 1

    await hass.services.async_call(
        "media_player",
        "media_previous_track",
        {"entity_id": "media_player.soundtouch_1"},
        True,
    )
    assert mocked_status.call_count == 4
    assert mocked_previous_track.call_count == 1


@patch("libsoundtouch.device.SoundTouchDevice.select_preset")
@patch("libsoundtouch.device.SoundTouchDevice.presets", side_effect=_mocked_presets)
async def test_play_media(
    mocked_presets, mocked_select_preset, mocked_status, mocked_volume, hass, one_device
):
    """Test play preset 1."""
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            "entity_id": "media_player.soundtouch_1",
            ATTR_MEDIA_CONTENT_TYPE: "PLAYLIST",
            ATTR_MEDIA_CONTENT_ID: 1,
        },
        True,
    )
    assert mocked_presets.call_count == 1
    assert mocked_select_preset.call_count == 1

    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            "entity_id": "media_player.soundtouch_1",
            ATTR_MEDIA_CONTENT_TYPE: "PLAYLIST",
            ATTR_MEDIA_CONTENT_ID: 2,
        },
        True,
    )
    assert mocked_presets.call_count == 2
    assert mocked_select_preset.call_count == 1


@patch("libsoundtouch.device.SoundTouchDevice.play_url")
async def test_play_media_url(
    mocked_play_url, mocked_status, mocked_volume, hass, one_device
):
    """Test play preset 1."""
    await setup_soundtouch(hass, DEVICE_1_CONFIG)

    assert one_device.call_count == 1
    assert mocked_status.call_count == 2
    assert mocked_volume.call_count == 2

    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            "entity_id": "media_player.soundtouch_1",
            ATTR_MEDIA_CONTENT_TYPE: "MUSIC",
            ATTR_MEDIA_CONTENT_ID: "http://fqdn/file.mp3",
        },
        True,
    )
    mocked_play_url.assert_called_with("http://fqdn/file.mp3")


@patch("libsoundtouch.device.SoundTouchDevice.create_zone")
async def test_play_everywhere(
    mocked_create_zone, mocked_status, mocked_volume, hass, two_zones
):
    """Test play everywhere."""
    mocked_device = two_zones
    await setup_soundtouch(hass, [DEVICE_1_CONFIG, DEVICE_2_CONFIG])

    assert mocked_device.call_count == 2
    assert mocked_status.call_count == 4
    assert mocked_volume.call_count == 4

    # one master, one slave => create zone
    await hass.services.async_call(
        soundtouch.DOMAIN,
        soundtouch.SERVICE_PLAY_EVERYWHERE,
        {"master": "media_player.soundtouch_1"},
        True,
    )
    assert mocked_create_zone.call_count == 1

    # unknown master, create zone must not be called
    await hass.services.async_call(
        soundtouch.DOMAIN,
        soundtouch.SERVICE_PLAY_EVERYWHERE,
        {"master": "media_player.entity_X"},
        True,
    )
    assert mocked_create_zone.call_count == 1

    # no slaves, create zone must not be called
    for entity in list(hass.data[DATA_SOUNDTOUCH]):
        if entity.entity_id == "media_player.soundtouch_1":
            continue
        hass.data[DATA_SOUNDTOUCH].remove(entity)
        await entity.async_remove()
    await hass.services.async_call(
        soundtouch.DOMAIN,
        soundtouch.SERVICE_PLAY_EVERYWHERE,
        {"master": "media_player.soundtouch_1"},
        True,
    )
    assert mocked_create_zone.call_count == 1


@patch("libsoundtouch.device.SoundTouchDevice.create_zone")
async def test_create_zone(
    mocked_create_zone, mocked_status, mocked_volume, hass, two_zones
):
    """Test creating a zone."""
    mocked_device = two_zones
    await setup_soundtouch(hass, [DEVICE_1_CONFIG, DEVICE_2_CONFIG])

    assert mocked_device.call_count == 2
    assert mocked_status.call_count == 4
    assert mocked_volume.call_count == 4

    # one master, one slave => create zone
    await hass.services.async_call(
        soundtouch.DOMAIN,
        soundtouch.SERVICE_CREATE_ZONE,
        {
            "master": "media_player.soundtouch_1",
            "slaves": ["media_player.soundtouch_2"],
        },
        True,
    )
    assert mocked_create_zone.call_count == 1

    # unknown master, create zone must not be called
    await hass.services.async_call(
        soundtouch.DOMAIN,
        soundtouch.SERVICE_CREATE_ZONE,
        {"master": "media_player.entity_X", "slaves": ["media_player.soundtouch_2"]},
        True,
    )
    assert mocked_create_zone.call_count == 1

    # no slaves, create zone must not be called
    await hass.services.async_call(
        soundtouch.DOMAIN,
        soundtouch.SERVICE_CREATE_ZONE,
        {"master": "media_player.soundtouch_1", "slaves": []},
        True,
    )
    assert mocked_create_zone.call_count == 1


@patch("libsoundtouch.device.SoundTouchDevice.remove_zone_slave")
async def test_remove_zone_slave(
    mocked_remove_zone_slave, mocked_status, mocked_volume, hass, two_zones
):
    """Test adding a slave to an existing zone."""
    mocked_device = two_zones
    await setup_soundtouch(hass, [DEVICE_1_CONFIG, DEVICE_2_CONFIG])

    assert mocked_device.call_count == 2
    assert mocked_status.call_count == 4
    assert mocked_volume.call_count == 4

    # remove one slave
    await hass.services.async_call(
        soundtouch.DOMAIN,
        soundtouch.SERVICE_REMOVE_ZONE_SLAVE,
        {
            "master": "media_player.soundtouch_1",
            "slaves": ["media_player.soundtouch_2"],
        },
        True,
    )
    assert mocked_remove_zone_slave.call_count == 1

    # unknown master. add zone slave is not called
    await hass.services.async_call(
        soundtouch.DOMAIN,
        soundtouch.SERVICE_REMOVE_ZONE_SLAVE,
        {"master": "media_player.entity_X", "slaves": ["media_player.soundtouch_2"]},
        True,
    )
    assert mocked_remove_zone_slave.call_count == 1

    # no slave to add, add zone slave is not called
    await hass.services.async_call(
        soundtouch.DOMAIN,
        soundtouch.SERVICE_REMOVE_ZONE_SLAVE,
        {"master": "media_player.soundtouch_1", "slaves": []},
        True,
    )
    assert mocked_remove_zone_slave.call_count == 1


@patch("libsoundtouch.device.SoundTouchDevice.add_zone_slave")
async def test_add_zone_slave(
    mocked_add_zone_slave, mocked_status, mocked_volume, hass, two_zones,
):
    """Test removing a slave from a zone."""
    mocked_device = two_zones
    await setup_soundtouch(hass, [DEVICE_1_CONFIG, DEVICE_2_CONFIG])

    assert mocked_device.call_count == 2
    assert mocked_status.call_count == 4
    assert mocked_volume.call_count == 4

    # add one slave
    await hass.services.async_call(
        soundtouch.DOMAIN,
        soundtouch.SERVICE_ADD_ZONE_SLAVE,
        {
            "master": "media_player.soundtouch_1",
            "slaves": ["media_player.soundtouch_2"],
        },
        True,
    )
    assert mocked_add_zone_slave.call_count == 1

    # unknown master, add zone slave is not called
    await hass.services.async_call(
        soundtouch.DOMAIN,
        soundtouch.SERVICE_ADD_ZONE_SLAVE,
        {"master": "media_player.entity_X", "slaves": ["media_player.soundtouch_2"]},
        True,
    )
    assert mocked_add_zone_slave.call_count == 1

    # no slave to add, add zone slave is not called
    await hass.services.async_call(
        soundtouch.DOMAIN,
        soundtouch.SERVICE_ADD_ZONE_SLAVE,
        {"master": "media_player.soundtouch_1", "slaves": ["media_player.entity_X"]},
        True,
    )
    assert mocked_add_zone_slave.call_count == 1


@patch("libsoundtouch.device.SoundTouchDevice.create_zone")
async def test_zone_attributes(
    mocked_create_zone, mocked_status, mocked_volume, hass, two_zones,
):
    """Test play everywhere."""
    mocked_device = two_zones
    await setup_soundtouch(hass, [DEVICE_1_CONFIG, DEVICE_2_CONFIG])

    assert mocked_device.call_count == 2
    assert mocked_status.call_count == 4
    assert mocked_volume.call_count == 4

    entity_1_state = hass.states.get("media_player.soundtouch_1")
    assert entity_1_state.attributes[ATTR_SOUNDTOUCH_ZONE]["is_master"]
    assert (
        entity_1_state.attributes[ATTR_SOUNDTOUCH_ZONE]["master"]
        == "media_player.soundtouch_1"
    )
    assert entity_1_state.attributes[ATTR_SOUNDTOUCH_ZONE]["slaves"] == [
        "media_player.soundtouch_2"
    ]
    assert entity_1_state.attributes[ATTR_SOUNDTOUCH_GROUP] == [
        "media_player.soundtouch_1",
        "media_player.soundtouch_2",
    ]
    entity_2_state = hass.states.get("media_player.soundtouch_2")
    assert not entity_2_state.attributes[ATTR_SOUNDTOUCH_ZONE]["is_master"]
    assert (
        entity_2_state.attributes[ATTR_SOUNDTOUCH_ZONE]["master"]
        == "media_player.soundtouch_1"
    )
    assert entity_2_state.attributes[ATTR_SOUNDTOUCH_ZONE]["slaves"] == [
        "media_player.soundtouch_2"
    ]
    assert entity_2_state.attributes[ATTR_SOUNDTOUCH_GROUP] == [
        "media_player.soundtouch_1",
        "media_player.soundtouch_2",
    ]

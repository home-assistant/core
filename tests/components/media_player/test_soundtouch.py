"""Test the Soundtouch component."""
import logging
import unittest
from unittest import mock
from libsoundtouch.device import SoundTouchDevice as STD, Status, Volume, \
    Preset, Config

from homeassistant.components.media_player import soundtouch
from homeassistant.const import (
    STATE_OFF, STATE_PAUSED, STATE_PLAYING)
from tests.common import get_test_home_assistant


class MockService:
    """Mock Soundtouch service."""

    def __init__(self, master, slaves):
        """Create a new service."""
        self.data = {
            "master": master,
            "slaves": slaves
        }


def _mock_soundtouch_device(*args, **kwargs):
    return MockDevice()


class MockDevice(STD):
    """Mock device."""

    def __init__(self):
        self._config = MockConfig


class MockConfig(Config):
    """Mock config."""

    def __init__(self):
        self._name = "name"


def _mocked_presets(*args, **kwargs):
    """Return a list of mocked presets."""
    return [MockPreset("1")]


class MockPreset(Preset):
    """Mock preset."""

    def __init__(self, id):
        self._id = id
        self._name = "preset"


class MockVolume(Volume):
    """Mock volume with value."""

    def __init__(self):
        self._actual = 12


class MockVolumeMuted(Volume):
    """Mock volume muted."""

    def __init__(self):
        self._actual = 12
        self._muted = True


class MockStatusStandby(Status):
    """Mock status standby."""

    def __init__(self):
        self._source = "STANDBY"


class MockStatusPlaying(Status):
    """Mock status playing media."""

    def __init__(self):
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
        self._source = ""
        self._play_status = "PAUSE_STATE"


def default_component():
    """Return a default component."""
    return {
        'host': '192.168.0.1',
        'port': 8090,
        'name': 'soundtouch'
    }


class TestSoundtouchMediaPlayer(unittest.TestCase):
    """Bose Soundtouch test class."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        logging.disable(logging.CRITICAL)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        logging.disable(logging.NOTSET)
        soundtouch.DEVICES = []
        self.hass.stop()

    @mock.patch('libsoundtouch.soundtouch_device', side_effect=None)
    def test_ensure_setup_config(self, mocked_sountouch_device):
        """Test setup OK."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        # soundtouch.DEVICES[0].entity_id = 'entity_1'
        self.assertEqual(len(soundtouch.DEVICES), 1)
        self.assertEqual(soundtouch.DEVICES[0].name, 'soundtouch')
        self.assertEqual(soundtouch.DEVICES[0].config['port'], 8090)
        self.assertEqual(mocked_sountouch_device.call_count, 1)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_update(self, mocked_sountouch_device, mocked_status,
                    mocked_volume):
        """Test update device state."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 1)
        self.assertEqual(mocked_volume.call_count, 1)
        soundtouch.DEVICES[0].update()
        self.assertEqual(mocked_status.call_count, 2)
        self.assertEqual(mocked_volume.call_count, 2)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status',
                side_effect=MockStatusPlaying)
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_playing_media(self, mocked_sountouch_device, mocked_status,
                           mocked_volume):
        """Test playing media info."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 1)
        self.assertEqual(mocked_volume.call_count, 1)
        self.assertEqual(soundtouch.DEVICES[0].state, STATE_PLAYING)
        self.assertEqual(soundtouch.DEVICES[0].media_image_url, "image.url")
        self.assertEqual(soundtouch.DEVICES[0].media_title, "artist - track")
        self.assertEqual(soundtouch.DEVICES[0].media_track, "track")
        self.assertEqual(soundtouch.DEVICES[0].media_artist, "artist")
        self.assertEqual(soundtouch.DEVICES[0].media_album_name, "album")
        self.assertEqual(soundtouch.DEVICES[0].media_duration, 1)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status',
                side_effect=MockStatusUnknown)
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_playing_unknown_media(self, mocked_sountouch_device,
                                   mocked_status, mocked_volume):
        """Test playing media info."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 1)
        self.assertEqual(mocked_volume.call_count, 1)
        self.assertEqual(soundtouch.DEVICES[0].media_title, None)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status',
                side_effect=MockStatusPlayingRadio)
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_playing_radio(self, mocked_sountouch_device, mocked_status,
                           mocked_volume):
        """Test playing radio info."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 1)
        self.assertEqual(mocked_volume.call_count, 1)
        self.assertEqual(soundtouch.DEVICES[0].state, STATE_PLAYING)
        self.assertEqual(soundtouch.DEVICES[0].media_image_url, "image.url")
        self.assertEqual(soundtouch.DEVICES[0].media_title, "station")
        self.assertEqual(soundtouch.DEVICES[0].media_track, None)
        self.assertEqual(soundtouch.DEVICES[0].media_artist, None)
        self.assertEqual(soundtouch.DEVICES[0].media_album_name, None)
        self.assertEqual(soundtouch.DEVICES[0].media_duration, None)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume',
                side_effect=MockVolume)
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_get_volume_level(self, mocked_sountouch_device, mocked_status,
                              mocked_volume):
        """Test volume level."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 1)
        self.assertEqual(mocked_volume.call_count, 1)
        self.assertEqual(soundtouch.DEVICES[0].volume_level, 0.12)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status',
                side_effect=MockStatusStandby)
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_get_state_off(self, mocked_sountouch_device, mocked_status,
                           mocked_volume):
        """Test state device is off."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 1)
        self.assertEqual(mocked_volume.call_count, 1)
        self.assertEqual(soundtouch.DEVICES[0].state, STATE_OFF)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status',
                side_effect=MockStatusPause)
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_get_state_pause(self, mocked_sountouch_device, mocked_status,
                             mocked_volume):
        """Test state device is paused."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 1)
        self.assertEqual(mocked_volume.call_count, 1)
        self.assertEqual(soundtouch.DEVICES[0].state, STATE_PAUSED)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume',
                side_effect=MockVolumeMuted)
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_is_muted(self, mocked_sountouch_device, mocked_status,
                      mocked_volume):
        """Test device volume is muted."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 1)
        self.assertEqual(mocked_volume.call_count, 1)
        self.assertEqual(soundtouch.DEVICES[0].is_volume_muted, True)

    @mock.patch('libsoundtouch.soundtouch_device')
    def test_media_commands(self, mocked_sountouch_device):
        """Test supported media commands."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(soundtouch.DEVICES[0].supported_media_commands, 1469)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.power_off')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_should_turn_off(self, mocked_sountouch_device, mocked_status,
                             mocked_volume, mocked_power_off):
        """Test device is turned off."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.DEVICES[0].turn_off()
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 2)
        self.assertEqual(mocked_volume.call_count, 1)
        self.assertEqual(mocked_power_off.call_count, 1)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.power_on')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_should_turn_on(self, mocked_sountouch_device, mocked_status,
                            mocked_volume, mocked_power_on):
        """Test device is turned on."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.DEVICES[0].turn_on()
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 2)
        self.assertEqual(mocked_volume.call_count, 1)
        self.assertEqual(mocked_power_on.call_count, 1)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume_up')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_volume_up(self, mocked_sountouch_device, mocked_status,
                       mocked_volume, mocked_volume_up):
        """Test volume up."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.DEVICES[0].volume_up()
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 1)
        self.assertEqual(mocked_volume.call_count, 2)
        self.assertEqual(mocked_volume_up.call_count, 1)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume_down')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_volume_down(self, mocked_sountouch_device, mocked_status,
                         mocked_volume, mocked_volume_down):
        """Test volume down."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.DEVICES[0].volume_down()
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 1)
        self.assertEqual(mocked_volume.call_count, 2)
        self.assertEqual(mocked_volume_down.call_count, 1)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.set_volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_set_volume_level(self, mocked_sountouch_device, mocked_status,
                              mocked_volume, mocked_set_volume):
        """Test set volume level."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.DEVICES[0].set_volume_level(0.17)
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 1)
        self.assertEqual(mocked_volume.call_count, 2)
        mocked_set_volume.assert_called_with(17)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.mute')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_mute(self, mocked_sountouch_device, mocked_status, mocked_volume,
                  mocked_mute):
        """Test mute volume."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.DEVICES[0].mute_volume(None)
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 1)
        self.assertEqual(mocked_volume.call_count, 2)
        self.assertEqual(mocked_mute.call_count, 1)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.play')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_play(self, mocked_sountouch_device, mocked_status, mocked_volume,
                  mocked_play):
        """Test play command."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.DEVICES[0].media_play()
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 2)
        self.assertEqual(mocked_volume.call_count, 1)
        self.assertEqual(mocked_play.call_count, 1)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.pause')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_pause(self, mocked_sountouch_device, mocked_status, mocked_volume,
                   mocked_pause):
        """Test pause command."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.DEVICES[0].media_pause()
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 2)
        self.assertEqual(mocked_volume.call_count, 1)
        self.assertEqual(mocked_pause.call_count, 1)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.play_pause')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_play_pause_play(self, mocked_sountouch_device, mocked_status,
                             mocked_volume, mocked_play_pause):
        """Test play/pause."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.DEVICES[0].media_play_pause()
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 2)
        self.assertEqual(mocked_volume.call_count, 1)
        self.assertEqual(mocked_play_pause.call_count, 1)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.previous_track')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.next_track')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_next_previous_track(self, mocked_sountouch_device, mocked_status,
                                 mocked_volume, mocked_next_track,
                                 mocked_previous_track):
        """Test next/previous track."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 1)
        self.assertEqual(mocked_volume.call_count, 1)
        soundtouch.DEVICES[0].media_next_track()
        self.assertEqual(mocked_status.call_count, 2)
        self.assertEqual(mocked_next_track.call_count, 1)
        soundtouch.DEVICES[0].media_previous_track()
        self.assertEqual(mocked_status.call_count, 3)
        self.assertEqual(mocked_previous_track.call_count, 1)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.select_preset')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.presets',
                side_effect=_mocked_presets)
    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_play_media(self, mocked_sountouch_device, mocked_status,
                        mocked_volume, mocked_presets, mocked_select_preset):
        """Test play preset 1."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        self.assertEqual(mocked_sountouch_device.call_count, 1)
        self.assertEqual(mocked_status.call_count, 1)
        self.assertEqual(mocked_volume.call_count, 1)
        soundtouch.DEVICES[0].play_media('PLAYLIST', 1)
        self.assertEqual(mocked_presets.call_count, 1)
        self.assertEqual(mocked_select_preset.call_count, 1)
        soundtouch.DEVICES[0].play_media('PLAYLIST', 2)
        self.assertEqual(mocked_presets.call_count, 2)
        self.assertEqual(mocked_select_preset.call_count, 1)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.create_zone')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_play_everywhere(self, mocked_sountouch_device, mocked_status,
                             mocked_volume, mocked_create_zone):
        """Test play everywhere."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.DEVICES[0].entity_id = "entity_1"
        soundtouch.DEVICES[1].entity_id = "entity_2"
        self.assertEqual(mocked_sountouch_device.call_count, 2)
        self.assertEqual(mocked_status.call_count, 2)
        self.assertEqual(mocked_volume.call_count, 2)

        # one master, one slave => create zone
        service = MockService("entity_1", [])
        soundtouch.play_everywhere_service(service)
        self.assertEqual(mocked_create_zone.call_count, 1)

        # unknown master. create zone is must not be called
        service = MockService("entity_X", [])
        soundtouch.play_everywhere_service(service)
        self.assertEqual(mocked_create_zone.call_count, 1)

        # no slaves, create zone must not be called
        soundtouch.DEVICES.pop(1)
        service = MockService("entity_1", [])
        soundtouch.play_everywhere_service(service)
        self.assertEqual(mocked_create_zone.call_count, 1)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.create_zone')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_create_zone(self, mocked_sountouch_device, mocked_status,
                         mocked_volume, mocked_create_zone):
        """Test creating a zone."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.DEVICES[0].entity_id = "entity_1"
        soundtouch.DEVICES[1].entity_id = "entity_2"
        self.assertEqual(mocked_sountouch_device.call_count, 2)
        self.assertEqual(mocked_status.call_count, 2)
        self.assertEqual(mocked_volume.call_count, 2)

        # one master, one slave => create zone
        service = MockService("entity_1", ["entity_2"])
        soundtouch.create_zone_service(service)
        self.assertEqual(mocked_create_zone.call_count, 1)

        # unknown master. create zone is must not be called
        service = MockService("entity_X", [])
        soundtouch.create_zone_service(service)
        self.assertEqual(mocked_create_zone.call_count, 1)

        # no slaves, create zone must not be called
        soundtouch.DEVICES.pop(1)
        service = MockService("entity_1", [])
        soundtouch.create_zone_service(service)
        self.assertEqual(mocked_create_zone.call_count, 1)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.add_zone_slave')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_add_zone_slave(self, mocked_sountouch_device, mocked_status,
                            mocked_volume, mocked_add_zone_slave):
        """Test adding a slave to an existing zone."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.DEVICES[0].entity_id = "entity_1"
        soundtouch.DEVICES[1].entity_id = "entity_2"
        self.assertEqual(mocked_sountouch_device.call_count, 2)
        self.assertEqual(mocked_status.call_count, 2)
        self.assertEqual(mocked_volume.call_count, 2)

        # remove one slave
        service = MockService("entity_1", ["entity_2"])
        soundtouch.add_zone_slave(service)
        self.assertEqual(mocked_add_zone_slave.call_count, 1)

        # unknown master. add zone slave is not called
        service = MockService("entity_X", ["entity_2"])
        soundtouch.add_zone_slave(service)
        self.assertEqual(mocked_add_zone_slave.call_count, 1)

        # no slave to add, add zone slave is not called
        service = MockService("entity_1", [])
        soundtouch.add_zone_slave(service)
        self.assertEqual(mocked_add_zone_slave.call_count, 1)

    @mock.patch('libsoundtouch.device.SoundTouchDevice.remove_zone_slave')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.volume')
    @mock.patch('libsoundtouch.device.SoundTouchDevice.status')
    @mock.patch('libsoundtouch.soundtouch_device',
                side_effect=_mock_soundtouch_device)
    def test_remove_zone_slave(self, mocked_sountouch_device, mocked_status,
                               mocked_volume, mocked_remove_zone_slave):
        """Test removing a slave from a zone."""
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.setup_platform(self.hass,
                                  default_component(),
                                  mock.MagicMock())
        soundtouch.DEVICES[0].entity_id = "entity_1"
        soundtouch.DEVICES[1].entity_id = "entity_2"
        self.assertEqual(mocked_sountouch_device.call_count, 2)
        self.assertEqual(mocked_status.call_count, 2)
        self.assertEqual(mocked_volume.call_count, 2)

        # remove one slave
        service = MockService("entity_1", ["entity_2"])
        soundtouch.remove_zone_slave(service)
        self.assertEqual(mocked_remove_zone_slave.call_count, 1)

        # unknown master. remove zone slave is not called
        service = MockService("entity_X", ["entity_2"])
        soundtouch.remove_zone_slave(service)
        self.assertEqual(mocked_remove_zone_slave.call_count, 1)

        # no slave to add, add zone slave is not called
        service = MockService("entity_1", [])
        soundtouch.remove_zone_slave(service)
        self.assertEqual(mocked_remove_zone_slave.call_count, 1)

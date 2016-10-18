"""Test the Soundtouch component."""
import logging
import unittest
from unittest import mock

from homeassistant.components.media_player import soundtouch
from homeassistant.components.media_player.soundtouch import SoundTouchDevice
from homeassistant.const import (
    STATE_OFF, STATE_UNKNOWN, STATE_PAUSED, STATE_PLAYING,
    STATE_UNAVAILABLE)
from tests.common import get_test_home_assistant


class MockService:
    """Mock Soundtouch service."""

    def __init__(self, master, slaves):
        """Create a new service."""
        self.data = {
            "master": master,
            "slaves": slaves
        }


class MockResponse:
    """Mock Soundtouch XML response."""

    def __init__(self, text):
        """Create new XML response."""
        self.text = text


def _mocked_volume_level(*args, **kwargs):
    if args[0] == 'http://192.168.0.1:8090/volume':
        return MockResponse("""<?xml version="1.0" encoding="UTF-8" ?>
<volume deviceID="MAC-1">
    <targetvolume>12</targetvolume>
    <actualvolume>12</actualvolume>
    <muteenabled>false</muteenabled>
</volume>
        """)


def _mock_send_volume_up(*args, **kwargs):
    if args[0] != 'http://192.168.0.1:8090/volume' \
            or args[1] != '<volume>17</volume>':
        raise Exception('Bad volume level')


def _mock_send_volume_down(*args, **kwargs):
    if args[0] != 'http://192.168.0.1:8090/volume' \
            or args[1] != '<volume>7</volume>':
        raise Exception('Bad volume level')


def _mock_send_mute(*args, **kwargs):
    if args[0] != 'http://192.168.0.1:8090/key' or args[1] not in [
            '<key state="press" sender="Gabbo">MUTE</key>',
            '<key state="release" sender="Gabbo">MUTE</key>']:
        raise Exception("unkown call")


def _mocked_volume_muted(*args, **kwargs):
    if args[0] == 'http://192.168.0.1:8090/volume':
        return MockResponse("""<?xml version="1.0" encoding="UTF-8" ?>
<volume deviceID="MAC-1">
    <targetvolume>0</targetvolume>
    <actualvolume>0</actualvolume>
    <muteenabled>false</muteenabled>
</volume>
        """)


def _mocked_state_off(*args, **kwargs):
    if args[0] == 'http://192.168.0.1:8090/now_playing':
        return MockResponse("""<?xml version="1.0" encoding="UTF-8" ?>
<nowPlaying deviceID="MAC-2" source="STANDBY">
    <ContentItem source="STANDBY" isPresetable="true"/>
</nowPlaying>""")


def _mocked_state_unavailable(*args, **kwargs):
    if args[0] == 'http://192.168.0.1:8090/now_playing':
        return MockResponse("""<?xml version="1.0" encoding="UTF-8" ?>
<nowPlaying deviceID="MAC-2" source="INVALID_SOURCE">
    <ContentItem source="INVALID_SOURCE" isPresetable="true"/>
</nowPlaying>""")


def _mocked_state_playing(*args, **kwargs):
    if args[0] == 'http://192.168.0.1:8090/now_playing':
        return MockResponse("""<?xml version="1.0" encoding="UTF-8" ?>
<nowPlaying deviceID="MAC-1" source="SPOTIFY" sourceAccount="xxx">
    <ContentItem source="SPOTIFY" type="uri" location="xxx"
        sourceAccount="xxx" isPresetable="true">
        <itemName>Afternoon Accoustic</itemName>
    </ContentItem>
    <track>Cherry Wine - Live</track>
    <artist>Hozier</artist>
    <album>Take Me to Church EP</album>
    <art artImageStatus="IMAGE_PRESENT">
        http://i.scdn.co/image/0f12b4c66fbd0XXX
    </art>
    <time total="239">196</time>
    <skipEnabled/>
    <favoriteEnabled/>
    <playStatus>PLAY_STATE</playStatus>
    <shuffleSetting>SHUFFLE_ON</shuffleSetting>
    <repeatSetting>REPEAT_OFF</repeatSetting>
    <skipPreviousEnabled/>
    <streamType>TRACK_ONDEMAND</streamType>
    <trackID>spotify:track:xxxx</trackID>
</nowPlaying>""")


def _mocked_state_playing_stored_music(*args, **kwargs):
    # pylint: disable=invalid-name
    if args[0] == 'http://192.168.0.1:8090/now_playing':
        return MockResponse("""<?xml version="1.0" encoding="UTF-8" ?>
<nowPlaying deviceID="MAC-1" source="STORED_MUSIC" sourceAccount="XXX">
    <ContentItem source="STORED_MUSIC" location="27$2521" sourceAccount="XXX"
        isPresetable="true">
        <itemName>System of a Down</itemName>
    </ContentItem>
    <track>Chop Suey!</track>
    <artist>System of a Down</artist>
    <album>Toxicity</album>
    <offset>5</offset>
    <art artImageStatus="SHOW_DEFAULT_IMAGE"/>
    <time total="210">7</time>
    <skipEnabled/>
    <playStatus>PLAY_STATE</playStatus>
    <shuffleSetting>SHUFFLE_OFF</shuffleSetting>
    <repeatSetting>REPEAT_OFF</repeatSetting>
    <skipPreviousEnabled/>
</nowPlaying>""")


def _mocked_state_playing_radio(*args, **kwargs):
    if args[0] == 'http://192.168.0.1:8090/now_playing':
        return MockResponse("""<?xml version="1.0" encoding="UTF-8" ?>
<nowPlaying deviceID="MAC-1" source="INTERNET_RADIO">
    <ContentItem source="INTERNET_RADIO" location="1307" sourceAccount=""
        isPresetable="true">
        <itemName>franceinfo</itemName>
    </ContentItem>
    <track></track>
    <artist></artist>
    <album></album>
    <stationName>franceinfo</stationName>
    <art artImageStatus="IMAGE_PRESENT">
        http://item.radio456.com/007452/logo/logo-1307.jpg
    </art>
    <playStatus>PLAY_STATE</playStatus>
    <description>MP3 64 kbps Paris France, La radio franceinfo vous propose
        à tout moment une information complète, des reportages, et des
        émissions d’actualité.
    </description>
    <stationLocation>Paris France</stationLocation>
</nowPlaying>""")


def _mocked_state_playing_unknown(*args, **kwargs):
    if args[0] == 'http://192.168.0.1:8090/now_playing':
        return MockResponse("""<?xml version="1.0" encoding="UTF-8" ?>
<nowPlaying deviceID="MAC-1" source="OTHER">
    <ContentItem source="OTHER" location="1307" sourceAccount=""
        isPresetable="true">
        <itemName>Other</itemName>
    </ContentItem>
    <track></track>
    <artist></artist>
    <album></album>
    <stationName>franceinfo</stationName>
    <art artImageStatus="IMAGE_PRESENT">
        http://item.radio456.com/007452/logo/logo-1307.jpg
    </art>
    <playStatus>PLAY_STATE</playStatus>
    <description>Other</description>
    <stationLocation>Other</stationLocation>
</nowPlaying>""")


def _mocked_state_pause(*args, **kwargs):
    if args[0] == 'http://192.168.0.1:8090/now_playing':
        return MockResponse("""<?xml version="1.0" encoding="UTF-8" ?>
<nowPlaying deviceID="MAC-1" source="SPOTIFY" sourceAccount="xxx">
    <ContentItem source="SPOTIFY" type="uri" location="xxx"
        sourceAccount="xxx" isPresetable="true">
        <itemName>Afternoon Accoustic</itemName>
    </ContentItem>
    <track>Cherry Wine - Live</track>
    <artist>Hozier</artist>
    <album>Take Me to Church EP</album>
    <art artImageStatus="IMAGE_PRESENT">
        http://i.scdn.co/image/0f12b4c66fbd023e6c74ce011c7d0f0ca1322c46
    </art>
    <time total="239">196</time>
    <skipEnabled/>
    <favoriteEnabled/>
    <playStatus>PAUSE_STATE</playStatus>
    <shuffleSetting>SHUFFLE_ON</shuffleSetting>
    <repeatSetting>REPEAT_OFF</repeatSetting>
    <skipPreviousEnabled/>
    <streamType>TRACK_ONDEMAND</streamType>
    <trackID>spotify:track:xxxx</trackID>
</nowPlaying>""")


def _mocked_state_unknown(*args, **kwargs):
    if args[0] == 'http://192.168.0.1:8090/now_playing':
        return MockResponse("""<?xml version="1.0" encoding="UTF-8" ?>
<nowPlaying deviceID="MAC-1" source="SPOTIFY" sourceAccount="xxx">
    <ContentItem source="SPOTIFY" type="uri" location="xxx"
        sourceAccount="xxx" isPresetable="true">
        <itemName>Afternoon Accoustic</itemName>
    </ContentItem>
    <track>Cherry Wine - Live</track>
    <artist>Hozier</artist>
    <album>Take Me to Church EP</album>
    <art artImageStatus="IMAGE_PRESENT">
        http://i.scdn.co/image/0f12b4c66fbd023e6c74ce011c7d0f0ca1322c46
    </art>
    <time total="239">196</time>
    <skipEnabled/>
    <favoriteEnabled/>
    <playStatus>OTHER</playStatus>
    <shuffleSetting>SHUFFLE_ON</shuffleSetting>
    <repeatSetting>REPEAT_OFF</repeatSetting>
    <skipPreviousEnabled/>
    <streamType>TRACK_ONDEMAND</streamType>
    <trackID>spotify:track:xxxx</trackID>
</nowPlaying>""")


def _mock_send_key_power(*args, **kwargs):
    if args[0] != 'http://192.168.0.1:8090/key' or args[1] not in [
            '<key state="press" sender="Gabbo">POWER</key>',
            '<key state="release" sender="Gabbo">POWER</key>']:
        raise Exception("unkown call")


def _mock_send_play(*args, **kwargs):
    if args[0] != 'http://192.168.0.1:8090/key' or args[1] not in [
            '<key state="press" sender="Gabbo">PLAY</key>',
            '<key state="release" sender="Gabbo">PLAY</key>']:
        raise Exception("unkown call")


def _mock_send_pause(*args, **kwargs):
    if args[0] != 'http://192.168.0.1:8090/key' or args[1] not in [
            '<key state="press" sender="Gabbo">PAUSE</key>',
            '<key state="release" sender="Gabbo">PAUSE</key>']:
        raise Exception("unkown call")


def _mock_send_next_track(*args, **kwargs):
    if args[0] != 'http://192.168.0.1:8090/key' or args[1] not in [
            '<key state="press" sender="Gabbo">NEXT_TRACK</key>',
            '<key state="release" sender="Gabbo">NEXT_TRACK</key>']:
        raise Exception("unkown call")


def _mock_send_previous_track(*args, **kwargs):
    if args[0] != 'http://192.168.0.1:8090/key' or args[1] not in [
            '<key state="press" sender="Gabbo">PREV_TRACK</key>',
            '<key state="release" sender="Gabbo">PREV_TRACK</key>']:
        raise Exception("unkown call")


def _mock_get_presets(*args, **kwargs):
    if args[0] == 'http://192.168.0.1:8090/presets':
        return MockResponse("""<?xml version="1.0" encoding="UTF-8" ?>
<presets>
    <preset id="1" createdOn="1476019956" updatedOn="1476019956">
        <ContentItem source="SPOTIFY" type="uri" location="YYYY"
            sourceAccount="YYYY" isPresetable="true">
            <itemName>Zedd</itemName>
        </ContentItem>
    </preset>
</presets>
        """)


def _mock_get_state_info(*args, **kwargs):
    if args[0] == 'http://192.168.88.1:8090/info':
        return MockResponse("""<?xml version="1.0" encoding="UTF-8" ?>
<info deviceID="00112233445566">
    <name>Home</name>
    <type>SoundTouch 20</type>
    <margeAccountUUID>XXXX</margeAccountUUID>
    <components>
        <component>
            <componentCategory>SCM</componentCategory>
            <softwareVersion>
                13.0.9.29919.1889959 epdbuild.trunk.cepeswbldXXX
            </softwareVersion>
            <serialNumber>XXXXX</serialNumber>
        </component>
        <component>
            <componentCategory>PackagedProduct</componentCategory>
            <serialNumber>XXXXX</serialNumber>
        </component>
    </components>
    <margeURL>https://streaming.bose.com</margeURL>
    <networkInfo type="SCM">
        <macAddress>00112233445566</macAddress>
        <ipAddress>192.168.88.1</ipAddress>
    </networkInfo>
    <networkInfo type="SMSC">
        <macAddress>00112233445566</macAddress>
        <ipAddress>192.168.88.1</ipAddress>
    </networkInfo>
    <moduleType>sm2</moduleType>
    <variant>spotty</variant>
    <variantMode>normal</variantMode>
    <countryCode>GB</countryCode>
    <regionCode>GB</regionCode>
</info>""")
    if args[0] == "http://192.168.0.1:8090/info":
        return MockResponse("""<?xml version="1.0" encoding="UTF-8" ?>
<info deviceID="778899AABBCC">
    <name>Room</name>
    <type>SoundTouch 10</type>
    <margeAccountUUID>XXXX</margeAccountUUID>
    <components>
        <component>
            <componentCategory>SCM</componentCategory>
            <softwareVersion>
                13.0.9.29919.1889959 epdbuild.trunk.cepeswbldXXX
            </softwareVersion>
            <serialNumber>XXXXX</serialNumber>
        </component>
        <component>
            <componentCategory>PackagedProduct</componentCategory>
            <serialNumber>XXXX</serialNumber>
        </component>
    </components>
    <margeURL>https://streaming.bose.com</margeURL>
    <networkInfo type="SCM">
        <macAddress>778899AABBCC</macAddress>
        <ipAddress>192.168.0.1</ipAddress>
    </networkInfo>
    <networkInfo type="SMSC">
        <macAddress>778899AABBCC</macAddress>
        <ipAddress>192.168.0.1</ipAddress>
    </networkInfo>
    <moduleType>sm2</moduleType>
    <variant>rhino</variant>
    <variantMode>normal</variantMode>
    <countryCode>GB</countryCode>
    <regionCode>GB</regionCode>
</info>""")


def _mock_create_zone(*args, **kwargs):
    if (args[0] != "http://192.168.88.1:8090/setZone" or
            args[1] != '<zone master="00112233445566" '
                       'senderIPAddress="192.168.88.1">'
                       '<member ipaddress="192.168.0.1">'
                       '778899AABBCC</member></zone>'):
        raise Exception("Bad argument")


def _mock_add_zone_slave(*args, **kwargs):
    if (args[0] != "http://192.168.88.1:8090/addZoneSlave" or
            args[1] != '<zone master="00112233445566">'
                       '<member ipaddress="192.168.0.1">'
                       '778899AABBCC</member></zone>'):
        raise Exception("Bad argument")


def _mock_remove_zone_slave(*args, **kwargs):
    if (args[0] != 'http://192.168.88.1:8090/removeZoneSlave' or
            args[1] != '<zone master="00112233445566">'
                       '<member ipaddress="192.168.0.1">'
                       '778899AABBCC</member></zone>'):
        raise Exception("Bad argument")


def _mock_select(*args, **kwargs):
    if args[0] != 'http://192.168.0.1:8090/select' \
            or 'location="YYYY"' not in args[1]:
        raise Exception('Wrong content')


class TestSoundtouchMediaPlayer(unittest.TestCase):
    """Bose Soundtouch test class."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        logging.disable(logging.CRITICAL)
        self.hass = get_test_home_assistant()
        soundtouch.setup_platform(self.hass,
                                  {
                                      'host': '192.168.0.1',
                                      'port': 8090,
                                      'name': 'soundtouch'
                                  },
                                  mock.MagicMock())
        soundtouch.DEVICES[0].entity_id = 'entity_1'

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        logging.disable(logging.NOTSET)
        soundtouch.DEVICES = []
        self.hass.stop()

    def test_ensure_setup_config(self):
        """Test setup OK."""
        self.assertEqual(len(soundtouch.DEVICES), 1)
        self.assertEqual(soundtouch.DEVICES[0].name, 'soundtouch')
        self.assertEqual(soundtouch.DEVICES[0].config['port'], 8090)

    @mock.patch('requests.get', side_effect=_mocked_state_off)
    def test_update(self, mock_state_off):
        """Test update device state."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(mock_state_off.call_count, 1)
        self.assertEqual(soundtouch.DEVICES[0].state, STATE_OFF)

    @mock.patch('requests.get', side_effect=_mocked_volume_level)
    def test_get_volume_level(self, mock_get):
        """Test volume level."""
        self.assertEqual(soundtouch.DEVICES[0].volume_level, 0.12)

    @mock.patch('requests.get', side_effect=_mocked_state_off)
    def test_get_state_off(self, mock_get):
        """Test state device is off."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].state, STATE_OFF)

    @mock.patch('requests.get', side_effect=_mocked_state_unavailable)
    def test_get_state_unavailable(self, mock_get):
        """Test state device is unavailable."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].state, STATE_UNAVAILABLE)

    @mock.patch('requests.get', side_effect=_mocked_state_playing)
    def test_get_state_playing(self, mock_get):
        """Test state device is playing."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].state, STATE_PLAYING)

    @mock.patch('requests.get', side_effect=_mocked_state_pause)
    def test_get_state_pause(self, mock_get):
        """Test state device is paused."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].state, STATE_PAUSED)

    @mock.patch('requests.get', side_effect=_mocked_state_unknown)
    def test_get_state_unkown(self, mock_get):
        """Test state device is unknown."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].state, STATE_UNKNOWN)
        self.assertEqual(mock_get.call_count, 1)

    @mock.patch('requests.get', side_effect=_mocked_volume_muted)
    def test_is_muted(self, mock_get):
        """Test device volume is muted."""
        self.assertEqual(soundtouch.DEVICES[0].is_volume_muted, True)

    def test_media_commands(self):
        """Test supported media commands."""
        self.assertEqual(soundtouch.DEVICES[0].supported_media_commands, 1469)

    @mock.patch('requests.post', side_effect=_mock_send_key_power)
    @mock.patch('requests.get', side_effect=_mocked_state_playing)
    def test_should_turn_off(self, mocked_get, mock_send_key):
        """Test device is turned off."""
        soundtouch.DEVICES[0].update()
        soundtouch.DEVICES[0].entity_id = 'entity_id'
        soundtouch.DEVICES[0].turn_off()
        self.assertEqual(mock_send_key.call_count, 2)
        self.assertEqual(mocked_get.call_count, 1)

    @mock.patch('requests.get', side_effect=_mocked_state_off)
    def test_should_not_turn_off_if_not_playing(self, mocked_get):
        # pylint: disable=invalid-name
        """Test don't send turn off command if device is not playing."""
        soundtouch.DEVICES[0].update()
        soundtouch.DEVICES[0].entity_id = 'entity_id'
        soundtouch.DEVICES[0].turn_off()
        self.assertEqual(mocked_get.call_count, 1)

    @mock.patch('requests.post', side_effect=_mock_send_key_power)
    @mock.patch('requests.get', side_effect=_mocked_state_off)
    def test_should_turn_on(self, mocked_get, mock_send_key):
        """Test device is turned on."""
        soundtouch.DEVICES[0].update()
        soundtouch.DEVICES[0].entity_id = 'entity_id'
        soundtouch.DEVICES[0].turn_on()
        self.assertEqual(mock_send_key.call_count, 2)
        self.assertEqual(mocked_get.call_count, 1)

    @mock.patch('requests.get', side_effect=_mocked_state_playing)
    def test_should_not_turn_on_if_playing(self, mocked_get):
        # pylint: disable=invalid-name
        """Test don't send turn on command if device is already playing."""
        soundtouch.DEVICES[0].update()
        soundtouch.DEVICES[0].entity_id = 'entity_id'
        soundtouch.DEVICES[0].turn_on()
        self.assertEqual(mocked_get.call_count, 1)

    @mock.patch('requests.post', side_effect=_mock_send_volume_up)
    @mock.patch('requests.get', side_effect=_mocked_volume_level)
    def test_volume_up(self, get_volume, send_volume):
        """Test volume up."""
        soundtouch.DEVICES[0].volume_up()
        self.assertEqual(get_volume.call_count, 1)
        self.assertEqual(send_volume.call_count, 1)

    @mock.patch('requests.post', side_effect=_mock_send_volume_down)
    @mock.patch('requests.get', side_effect=_mocked_volume_level)
    def test_volume_down(self, get_volume, send_volume):
        """Test volume down."""
        soundtouch.DEVICES[0].volume_down()
        self.assertEqual(get_volume.call_count, 1)
        self.assertEqual(send_volume.call_count, 1)

    @mock.patch('requests.post', side_effect=_mock_send_volume_up)
    def test_set_volume_level(self, send_volume):
        """Test set volume level."""
        soundtouch.DEVICES[0].set_volume_level(0.17)
        self.assertEqual(send_volume.call_count, 1)

    @mock.patch('requests.post', side_effect=_mock_send_mute)
    def test_mute(self, send_mute):
        """Test mute volume."""
        soundtouch.DEVICES[0].mute_volume(None)
        self.assertEqual(send_mute.call_count, 2)

    @mock.patch('requests.post', side_effect=_mock_send_play)
    def test_play(self, send_play):
        """Test play command."""
        soundtouch.DEVICES[0].media_play()
        self.assertEqual(send_play.call_count, 2)

    @mock.patch('requests.post', side_effect=_mock_send_pause)
    def test_pause(self, send_pause):
        """Test pause command."""
        soundtouch.DEVICES[0].media_pause()
        self.assertEqual(send_pause.call_count, 2)

    @mock.patch('requests.post', side_effect=_mock_send_play)
    @mock.patch('requests.get', side_effect=_mocked_state_pause)
    def test_play_pause_play(self, get_status, send_play):
        """Test play/pause if device is in pause."""
        soundtouch.DEVICES[0].update()
        soundtouch.DEVICES[0].media_play_pause()
        self.assertEqual(get_status.call_count, 1)
        self.assertEqual(send_play.call_count, 2)

    @mock.patch('requests.post', side_effect=_mock_send_pause)
    @mock.patch('requests.get', side_effect=_mocked_state_playing)
    def test_play_pause_pause(self, get_status, send_pause):
        """Test play/pause if device is playing."""
        soundtouch.DEVICES[0].update()
        soundtouch.DEVICES[0].media_play_pause()
        self.assertEqual(get_status.call_count, 1)
        self.assertEqual(send_pause.call_count, 2)

    @mock.patch('requests.post', side_effect=_mock_send_next_track)
    def test_next_track(self, mock_next_track):
        """Test next track."""
        soundtouch.DEVICES[0].media_next_track()
        self.assertEqual(mock_next_track.call_count, 2)

    @mock.patch('requests.post', side_effect=_mock_send_previous_track)
    def test_previous_track(self, previous_track):
        """Test previous track."""
        soundtouch.DEVICES[0].media_previous_track()
        self.assertEqual(previous_track.call_count, 2)

    @mock.patch('requests.get', side_effect=_mocked_state_playing)
    def test_get_image_url(self, get_status):
        """Test get Image URL if present."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].media_image_url.strip(),
                         "http://i.scdn.co/image/0f12b4c66fbd0XXX")
        self.assertEqual(get_status.call_count, 1)

    @mock.patch('requests.get', side_effect=_mocked_state_playing_stored_music)
    def test_get_image_url_if_no_image(self, state_playing_stored_music):
        """Test returning None as image URL if no image is available."""
        soundtouch.DEVICES[0].update()
        self.assertIsNone(soundtouch.DEVICES[0].media_image_url)
        self.assertEqual(state_playing_stored_music.call_count, 1)

    @mock.patch('requests.get', side_effect=_mocked_state_playing)
    def test_get_media_title(self, state_playing):
        """Test media title for streaming/stored music."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].media_title,
                         "Hozier - Cherry Wine - Live")
        self.assertEqual(state_playing.call_count, 1)

    @mock.patch('requests.get', side_effect=_mocked_state_playing_radio)
    def test_get_media_title_radio(self, state_playing_radio):
        """Test media title for radio."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].media_title, "franceinfo")
        self.assertEqual(state_playing_radio.call_count, 1)

    @mock.patch('requests.get', side_effect=_mocked_state_playing)
    def test_get_media_track(self, state_playing):
        """Test media track for streaming/stored music..."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].media_track,
                         "Cherry Wine - Live")
        self.assertEqual(state_playing.call_count, 1)

    @mock.patch('requests.get', side_effect=_mocked_state_playing_radio)
    def test_get_media_track_radio(self, state_playing_radio):
        """Test media track for radio."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].media_track, None)
        self.assertEqual(state_playing_radio.call_count, 1)

    @mock.patch('requests.get', side_effect=_mocked_state_playing_unknown)
    def test_get_media_title_unknown(self, state_playing_unknown):
        """Test media title is None if unable to get media title."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].media_title, None)
        self.assertEqual(state_playing_unknown.call_count, 1)

    @mock.patch('requests.get', side_effect=_mocked_state_playing)
    def test_get_media_artist(self, state_playing):
        """Test artist for streaming/stored music."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].media_artist, "Hozier")
        self.assertEqual(state_playing.call_count, 1)

    @mock.patch('requests.get', side_effect=_mocked_state_playing_radio)
    def test_get_media_artist_radio(self, state_playing_radio):
        """Test get artist is None for radio."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].media_artist, None)
        self.assertEqual(state_playing_radio.call_count, 1)

    @mock.patch('requests.get', side_effect=_mocked_state_playing)
    def test_get_media_album(self, state_playing):
        """Test media album for streaming/stored music."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].media_album_name,
                         "Take Me to Church EP")
        self.assertEqual(state_playing.call_count, 1)

    @mock.patch('requests.get', side_effect=_mocked_state_playing_radio)
    def test_get_media_album_radio(self, state_playing_radio):
        """Test media album is None for radio."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].media_album_name, None)
        self.assertEqual(state_playing_radio.call_count, 1)

    @mock.patch('requests.get', side_effect=_mocked_state_playing)
    def test_get_media_duration(self, state_playing):
        """Test media duration for streaming/stored music."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].media_duration, 239)
        self.assertEqual(state_playing.call_count, 1)

    @mock.patch('requests.get', side_effect=_mocked_state_playing_radio)
    def test_get_media_duration_radio(self, state_playing_radio):
        """Test media duration for streaming/stored music."""
        soundtouch.DEVICES[0].update()
        self.assertEqual(soundtouch.DEVICES[0].media_duration, None)
        self.assertEqual(state_playing_radio.call_count, 1)

    @mock.patch('requests.post', side_effect=_mock_select)
    @mock.patch('requests.get', side_effect=_mock_get_presets)
    def test_play_media(self, presets, select):
        """Test play preset 1."""
        soundtouch.DEVICES[0].play_media('PLAYLIST', 1)
        self.assertEqual(presets.call_count, 1)
        self.assertEqual(select.call_count, 1)

    @mock.patch('requests.get', side_effect=_mock_get_presets)
    def test_play_media_unknown(self, mock_presets):
        """Test play unkown preset (valid is 1)."""
        soundtouch.DEVICES[0].play_media('PLAYLIST', 8)
        self.assertEqual(mock_presets.call_count, 1)

    @mock.patch('requests.post', side_effect=_mock_create_zone)
    @mock.patch('requests.get', side_effect=_mock_get_state_info)
    def test_play_everywhere(self, get_state_info, create_zone):
        """Test play everywhere with master device 'master_id'."""
        device1 = SoundTouchDevice("device1", {
            "host": "192.168.88.1",
            "port": 8090
        })
        device1.entity_id = "master_id"
        soundtouch.DEVICES.append(device1)
        service = MockService("master_id", [])
        soundtouch.play_everywhere_service(service)
        self.assertEqual(get_state_info.call_count, 2)
        self.assertEqual(create_zone.call_count, 1)

    def test_play_everywhere_without_master(self):
        # pylint: disable=invalid-name, no-self-use
        """Test play everywhere without master do nothing."""
        service = MockService("master_id", [])
        soundtouch.play_everywhere_service(service)

    def test_play_everywhere_without_slaves(self):
        # pylint: disable=invalid-name, no-self-use
        """Test play everywhere without slaves do nothing."""
        service = MockService("entity_1", [])
        soundtouch.play_everywhere_service(service)

    @mock.patch('requests.post', side_effect=_mock_create_zone)
    @mock.patch('requests.get', side_effect=_mock_get_state_info)
    def test_create_zone(self, get_state_info, create_zone):
        """Test creating a zone with 1 master and 1 slave."""
        device1 = SoundTouchDevice("device1", {
            "host": "192.168.88.1",
            "port": 8090
        })
        device1.entity_id = "master_id"
        soundtouch.DEVICES.append(device1)
        service = MockService("master_id", ["entity_1"])
        soundtouch.create_zone_service(service)
        self.assertEqual(get_state_info.call_count, 2)
        self.assertEqual(create_zone.call_count, 1)

    def test_create_zone_without_master(self):
        # pylint: disable= no-self-use
        """Test creating a zone without master do nothing."""
        service = MockService("master_id", [])
        soundtouch.create_zone_service(service)

    def test_create_zone_without_slaves(self):
        # pylint: disable=no-self-use
        """Test creating a zone without slave(s) do nothing."""
        service = MockService("entity_1", [])
        soundtouch.create_zone_service(service)

    @mock.patch('requests.post', side_effect=_mock_add_zone_slave)
    @mock.patch('requests.get', side_effect=_mock_get_state_info)
    def test_add_zone_slave(self, get_state_info, add_zone_slave):
        """Test adding a slave to an existing zone."""
        device1 = SoundTouchDevice("device1", {
            "host": "192.168.88.1",
            "port": 8090
        })
        device1.entity_id = "master_id"
        soundtouch.DEVICES.append(device1)
        service = MockService("master_id", ["entity_1"])
        soundtouch.add_zone_slave(service)
        self.assertEqual(get_state_info.call_count, 2)
        self.assertEqual(add_zone_slave.call_count, 1)

    def test_add_zone_slave_without_master(self):
        # pylint: disable=invalid-name, no-self-use
        """Test adding a slave to a zone without a master do nothing."""
        service = MockService("master_id", [])
        soundtouch.add_zone_slave(service)

    def test_add_zone_slave_without_slaves(self):
        # pylint: disable=invalid-name, no-self-use
        """Test adding a slave without slave do nothing."""
        service = MockService("entity_1", [])
        soundtouch.add_zone_slave(service)

    @mock.patch('requests.post', side_effect=_mock_remove_zone_slave)
    @mock.patch('requests.get', side_effect=_mock_get_state_info)
    def test_remove_zone_slave(self, get_state_info, remove_zone_slave):
        """Test removing a slave from a zone."""
        device1 = SoundTouchDevice("device1", {
            "host": "192.168.88.1",
            "port": 8090
        })
        device1.entity_id = "master_id"
        soundtouch.DEVICES.append(device1)
        service = MockService("master_id", ["entity_1"])
        soundtouch.remove_zone_slave(service)
        self.assertEqual(get_state_info.call_count, 2)
        self.assertEqual(remove_zone_slave.call_count, 1)

    def test_remove_zone_slave_without_master(self):
        # pylint: disable=invalid-name, no-self-use
        """Test removing a slave zone without master do nothing."""
        service = MockService("master_id", [])
        soundtouch.remove_zone_slave(service)

    def test_remove_zone_slave_without_slaves(self):
        # pylint: disable=invalid-name, no-self-use
        """Test removing a slave zone without slave to remove do nothing."""
        service = MockService("entity_1", [])
        soundtouch.remove_zone_slave(service)

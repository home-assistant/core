"""The tests for the DirecTV Media player platform."""
import unittest
from unittest.mock import patch, Mock, MagicMock


from datetime import datetime, timedelta
import logging
import sys

from homeassistant.setup import setup_component
import homeassistant.components.media_player as mp
from homeassistant.components.media_player.directv import (
    ATTR_MEDIA_CURRENTLY_RECORDING, ATTR_MEDIA_RATING, ATTR_MEDIA_RECORDED,
    ATTR_MEDIA_START_TIME, DATA_DIRECTV, DEFAULT_DEVICE, DEFAULT_PORT,
    setup_platform)
from homeassistant.const import (
    CONF_DEVICE, CONF_HOST, CONF_NAME, CONF_PORT, STATE_OFF, STATE_PAUSED,
    STATE_PLAYING)
import homeassistant.util.dt as dt_util

from tests.common import get_test_home_assistant
from tests.components.media_player import common


IP_ADDRESS = '127.0.0.1'

WORKING_CONFIG = {
    CONF_HOST: IP_ADDRESS,
    CONF_NAME: 'Main DVR',
    CONF_PORT: DEFAULT_PORT,
    CONF_DEVICE: DEFAULT_DEVICE
}

DISCOVERY_INFO = {
    'host': IP_ADDRESS,
    'serial': 1234
}

LOCATIONS = [
    {
        'locationName': 'Main DVR',
        'clientAddr': DEFAULT_DEVICE
    }
]

LIVE = {
    "callsign": "CNNHD",
    "date": "20181110",
    "duration": 3600,
    "isOffAir": False,
    "isPclocked": 1,
    "isPpv": False,
    "isRecording": False,
    "isVod": False,
    "major": 202,
    "minor": 65535,
    "offset": 1,
    "programId": "102454523",
    "rating": "No Rating",
    "startTime": 1541876400,
    "stationId": 3900947,
    "title": "CNN Newsroom With Fredricka Whitfield"
}

RECORDING = {
    "callsign": "CNNHD",
    "date": "20181110",
    "duration": 3600,
    "isOffAir": False,
    "isPclocked": 1,
    "isPpv": False,
    "isRecording": True,
    "isVod": False,
    "major": 202,
    "minor": 65535,
    "offset": 1,
    "programId": "102454523",
    "rating": "No Rating",
    "startTime": 1541876400,
    "stationId": 3900947,
    "title": "CNN Newsroom With Fredricka Whitfield",
    'uniqueId': '12345',
    'episodeTitle': 'CNN Recorded'
}

_LOGGER = logging.getLogger(__name__)


class mockDIRECTVClass:
    """A fake DirecTV DVR device."""

    def __init__(self, ip, port=8080, clientAddr='0'):
        """Initialize the fake DirecTV device."""
        self._host = ip
        self._port = port
        self._device = clientAddr
        self._standby = True
        self._play = False

        _LOGGER.debug("INIT with host: %s, port: %s, device: %s",
                      self._host, self._port, self._device)

        self._locations = LOCATIONS

        self.attributes = LIVE

    def get_locations(self):
        """Mock for get_locations method."""
        _LOGGER.debug("get_locations called")
        test_locations = {
            'locations': self._locations,
            'status': {
                'code': 200,
                'commandResult': 0,
                'msg': 'OK.',
                'query': '/info/getLocations'
            }
        }

        return test_locations

    def get_standby(self):
        """Mock for get_standby method."""
        _LOGGER.debug("STANDBY is: %s", self._standby)
        return self._standby

    def get_tuned(self):
        """Mock for get_tuned method."""
        _LOGGER.debug("get_tuned called")
        if self._play:
            self.attributes['offset'] = self.attributes['offset']+1

        test_attributes = self.attributes
        test_attributes['status'] = {
            "code": 200,
            "commandResult": 0,
            "msg": "OK.",
            "query": "/tv/getTuned"
        }
        return test_attributes

    def key_press(self, keypress):
        """Mock for key_press method."""
        _LOGGER.debug("Key Press: %s", keypress)
        if keypress == 'poweron':
            self._standby = False
            self._play = True
        elif keypress == 'poweroff':
            self._standby = True
            self._play = False
        elif keypress == 'play':
            self._play = True
        elif keypress == 'pause' or keypress == 'stop':
            self._play = False

    def tune_channel(self, source):
        """Mock for tune_channel method."""
        _LOGGER.debug("Change channel %s", source)
        self.attributes['major'] = int(source)


class TestSetupDirectvMediaPlayer(unittest.TestCase):
    """Test the different possibilities for setting up DirecTV media player."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        # Mocking DIRECTV class in DirectPy with our own.
        self.directpy_mock = MagicMock()
        modules = {
            'DirectPy': self.directpy_mock
        }
        self.module_patcher = patch.dict('sys.modules', modules)
        self.module_patcher.start()
        import DirectPy
        DirectPy.DIRECTV = mockDIRECTVClass

        self.addCleanup(self.tearDown)

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()
        self.module_patcher.stop()

    def test_setup_platform_config(self):
        """Test setting up the platform from configuration."""
        add_entities = Mock()
        setup_platform(
            self.hass, WORKING_CONFIG, add_entities)
        assert add_entities.call_count == 1
        assert len(self.hass.data[DATA_DIRECTV]) == 1
        assert (WORKING_CONFIG[CONF_HOST], WORKING_CONFIG[CONF_DEVICE]) in\
            self.hass.data[DATA_DIRECTV]

    def test_setup_platform_discover(self):
        """Test setting up the platform from discovery."""
        add_entities = Mock()
        setup_platform(self.hass, {}, add_entities,
                       discovery_info=DISCOVERY_INFO)
        assert add_entities.call_count == 1

    def test_setup_platform_discover_duplicate(self):
        """Test no duplicate entities are created."""
        add_entities = Mock()
        setup_platform(
            self.hass, WORKING_CONFIG, add_entities)
        setup_platform(self.hass, {}, add_entities,
                       discovery_info=DISCOVERY_INFO)
        assert add_entities.call_count == 2
        assert len(self.hass.data[DATA_DIRECTV]) == 1

    def test_setup_platform_discover_client(self):
        """Test additional devices are discovered."""
        add_entities = Mock()

        LOCATIONS.append({
            'locationName': 'Client 1',
            'clientAddr': '1'
        })
        LOCATIONS.append({
            'locationName': 'Client 2',
            'clientAddr': '2'
        })

        setup_platform(
            self.hass, WORKING_CONFIG, add_entities)
        setup_platform(self.hass, {}, add_entities,
                       discovery_info=DISCOVERY_INFO)
        del LOCATIONS[-1]
        del LOCATIONS[-1]
        assert add_entities.call_count == 2
        assert len(self.hass.data[DATA_DIRECTV]) == 3
        assert (IP_ADDRESS, '1') in self.hass.data[DATA_DIRECTV]
        assert (IP_ADDRESS, '2') in self.hass.data[DATA_DIRECTV]


class TestDirectvMediaPlayer(unittest.TestCase):
    """Test the DirecTV media player."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.start()

        # Mocking DIRECTV class in DirectPy with our own.
        self.current_directpy = sys.modules.get('DirectPy')
        sys.modules['DirectPy'] = MagicMock()
        import DirectPy
        DirectPy.DIRECTV = mockDIRECTVClass

        self.addCleanup(self.tearDown)

        self.main_entity_id = 'media_player.main_dvr'
        self.client_entity_id = 'media_player.client_dvr'
        self.config = {
            'media_player': [{
                'platform': 'directv',
                'name': 'Main DVR',
                'host': IP_ADDRESS,
                'port': DEFAULT_PORT,
                'device': DEFAULT_DEVICE
                }, {
                'platform': 'directv',
                'name': 'Client DVR',
                'host': IP_ADDRESS,
                'port': DEFAULT_PORT,
                'device': '1'
                }
            ]
        }

        setup_component(self.hass, mp.DOMAIN, self.config)
        self.hass.block_till_done()

        self.main_media_entity = self.hass.data['media_player'].get_entity(
            self.main_entity_id)

        self.client_media_entity = self.hass.data['media_player'].get_entity(
            self.client_entity_id)

        # Set the client so it seems a recording is being watched.
        self.client_media_entity.dtv.attributes = RECORDING
        # Clients do not support turning on, setting it as client is on here.
        self.client_media_entity.dtv._standby = False

        self.main_media_entity.schedule_update_ha_state(True)
        self.client_media_entity.schedule_update_ha_state(True)
        self.hass.block_till_done()

        self.now = datetime(2018, 11, 19, 20, 0, 0, tzinfo=dt_util.UTC)

    def tearDown(self):
        """Stop everything that was started."""
        sys.modules['DirectPy'] = self.current_directpy
        self.hass.stop()

    def test_supported_features(self):
        """Test supported features."""
        # Features supported for main DVR
        assert mp.SUPPORT_PAUSE | mp.SUPPORT_TURN_ON | mp.SUPPORT_TURN_OFF |\
            mp.SUPPORT_PLAY_MEDIA | mp.SUPPORT_SELECT_SOURCE |\
            mp.SUPPORT_STOP | mp.SUPPORT_NEXT_TRACK |\
            mp.SUPPORT_PREVIOUS_TRACK | mp.SUPPORT_PLAY ==\
            self.main_media_entity.supported_features

        # Feature supported for clients.
        assert mp.SUPPORT_PAUSE |\
            mp.SUPPORT_PLAY_MEDIA | mp.SUPPORT_SELECT_SOURCE |\
            mp.SUPPORT_STOP | mp.SUPPORT_NEXT_TRACK |\
            mp.SUPPORT_PREVIOUS_TRACK | mp.SUPPORT_PLAY ==\
            self.client_media_entity.supported_features

    def test_check_attributes(self):
        """Test attributes."""
        # Start playing TV
        with patch('homeassistant.helpers.condition.dt_util.now',
                   return_value=self.now):
            common.media_play(self.hass, self.client_entity_id)
            self.hass.block_till_done()

        state = self.hass.states.get(self.client_entity_id)
        assert state.state == STATE_PLAYING

        assert state.attributes.get(mp.ATTR_MEDIA_CONTENT_ID) == \
            RECORDING['programId']
        assert state.attributes.get(mp.ATTR_MEDIA_CONTENT_TYPE) == \
            mp.MEDIA_TYPE_TVSHOW
        assert state.attributes.get(mp.ATTR_MEDIA_DURATION) == \
            RECORDING['duration']
        assert state.attributes.get(mp.ATTR_MEDIA_POSITION) == 2
        assert state.attributes.get(mp.ATTR_MEDIA_POSITION_UPDATED_AT) == \
            self.now
        assert state.attributes.get(mp.ATTR_MEDIA_TITLE) == \
            RECORDING['title']
        assert state.attributes.get(mp.ATTR_MEDIA_SERIES_TITLE) == \
            RECORDING['episodeTitle']
        assert state.attributes.get(mp.ATTR_MEDIA_CHANNEL) == \
            "{} ({})".format(RECORDING['callsign'], RECORDING['major'])
        assert state.attributes.get(mp.ATTR_INPUT_SOURCE) == \
            RECORDING['major']
        assert state.attributes.get(ATTR_MEDIA_CURRENTLY_RECORDING) == \
            RECORDING['isRecording']
        assert state.attributes.get(ATTR_MEDIA_RATING) == \
            RECORDING['rating']
        assert state.attributes.get(ATTR_MEDIA_RECORDED)
        assert state.attributes.get(ATTR_MEDIA_START_TIME) == \
            datetime(2018, 11, 10, 19, 0, tzinfo=dt_util.UTC)

        # Test to make sure that ATTR_MEDIA_POSITION_UPDATED_AT is not
        # updated if TV is paused.
        with patch('homeassistant.helpers.condition.dt_util.now',
                   return_value=self.now + timedelta(minutes=5)):
            common.media_pause(self.hass, self.client_entity_id)
            self.hass.block_till_done()

        state = self.hass.states.get(self.client_entity_id)
        assert state.state == STATE_PAUSED
        assert state.attributes.get(mp.ATTR_MEDIA_POSITION_UPDATED_AT) == \
            self.now

    def test_main_services(self):
        """Test the different services."""
        dtv_inst = self.main_media_entity.dtv

        # DVR starts in turned off state.
        state = self.hass.states.get(self.main_entity_id)
        assert state.state == STATE_OFF

        # All these should call key_press in our class.
        with patch.object(dtv_inst, 'key_press',
                          wraps=dtv_inst.key_press) as mock_key_press, \
            patch.object(dtv_inst, 'tune_channel',
                         wraps=dtv_inst.tune_channel) as mock_tune_channel, \
            patch.object(dtv_inst, 'get_tuned',
                         wraps=dtv_inst.get_tuned) as mock_get_tuned, \
            patch.object(dtv_inst, 'get_standby',
                         wraps=dtv_inst.get_standby) as mock_get_standby:

            # Turn main DVR on. When turning on DVR is playing.
            common.turn_on(self.hass, self.main_entity_id)
            self.hass.block_till_done()
            mock_key_press.assert_called_with('poweron')
            state = self.hass.states.get(self.main_entity_id)
            assert state.state == STATE_PLAYING

            # Pause live TV.
            common.media_pause(self.hass, self.main_entity_id)
            self.hass.block_till_done()
            mock_key_press.assert_called_with('pause')
            state = self.hass.states.get(self.main_entity_id)
            assert state.state == STATE_PAUSED

            # Start play again for live TV.
            common.media_play(self.hass, self.main_entity_id)
            self.hass.block_till_done()
            mock_key_press.assert_called_with('play')
            state = self.hass.states.get(self.main_entity_id)
            assert state.state == STATE_PLAYING

            # Change channel, currently it should be 202
            assert state.attributes.get('source') == 202
            common.select_source(self.hass, 7, self.main_entity_id)
            self.hass.block_till_done()
            mock_tune_channel.assert_called_with('7')
            state = self.hass.states.get(self.main_entity_id)
            assert state.attributes.get('source') == 7

            # Stop live TV.
            common.media_stop(self.hass, self.main_entity_id)
            self.hass.block_till_done()
            mock_key_press.assert_called_with('stop')
            state = self.hass.states.get(self.main_entity_id)
            assert state.state == STATE_PAUSED

            # Turn main DVR off.
            common.turn_off(self.hass, self.main_entity_id)
            self.hass.block_till_done()
            mock_key_press.assert_called_with('poweroff')
            state = self.hass.states.get(self.main_entity_id)
            assert state.state == STATE_OFF

            # There should have been 6 calls to check if DVR is in standby
            assert 6 == mock_get_standby.call_count
            # There should be 5 calls to get current info (only 1 time it will
            # not be called as DVR is in standby.)
            assert 5 == mock_get_tuned.call_count

    def test_available(self):
        """Test available status."""
        # Confirm service is currently set to available.
        assert self.main_media_entity.available

        # Make update fail (i.e. DVR offline)
        dtv = self.main_media_entity.dtv
        self.main_media_entity.dtv = None
        self.main_media_entity.schedule_update_ha_state(True)
        self.hass.block_till_done()
        assert not self.main_media_entity.available

        # Make update work again (i.e. DVR back online)
        self.main_media_entity.dtv = dtv
        self.main_media_entity.schedule_update_ha_state(True)
        self.hass.block_till_done()
        assert self.main_media_entity.available

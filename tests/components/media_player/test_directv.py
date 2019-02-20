"""The tests for the DirecTV Media player platform."""
from unittest.mock import call, patch

from datetime import datetime, timedelta
import requests
import pytest

import homeassistant.components.media_player as mp
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_CONTENT_TYPE, ATTR_MEDIA_ENQUEUE, DOMAIN,
    SERVICE_PLAY_MEDIA)
from homeassistant.components.media_player.directv import (
    ATTR_MEDIA_CURRENTLY_RECORDING, ATTR_MEDIA_RATING, ATTR_MEDIA_RECORDED,
    ATTR_MEDIA_START_TIME, DEFAULT_DEVICE, DEFAULT_PORT)
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_DEVICE, CONF_HOST, CONF_NAME, CONF_PORT,
    SERVICE_MEDIA_NEXT_TRACK, SERVICE_MEDIA_PAUSE, SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK, SERVICE_MEDIA_STOP, SERVICE_TURN_OFF,
    SERVICE_TURN_ON, STATE_OFF, STATE_PAUSED, STATE_PLAYING, STATE_UNAVAILABLE)
from homeassistant.helpers.discovery import async_load_platform
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockDependency, async_fire_time_changed

CLIENT_ENTITY_ID = 'media_player.client_dvr'
MAIN_ENTITY_ID = 'media_player.main_dvr'
IP_ADDRESS = '127.0.0.1'

DISCOVERY_INFO = {
    'host': IP_ADDRESS,
    'serial': 1234
}

LIVE = {
    "callsign": "HASSTV",
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
    "title": "Using Home Assistant to automate your home"
}

LOCATIONS = [
    {
        'locationName': 'Main DVR',
        'clientAddr': DEFAULT_DEVICE
    }
]

RECORDING = {
    "callsign": "HASSTV",
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
    "title": "Using Home Assistant to automate your home",
    'uniqueId': '12345',
    'episodeTitle': 'Configure DirecTV platform.'
}

WORKING_CONFIG = {
    'media_player': {
        'platform': 'directv',
        CONF_HOST: IP_ADDRESS,
        CONF_NAME: 'Main DVR',
        CONF_PORT: DEFAULT_PORT,
        CONF_DEVICE: DEFAULT_DEVICE
    }
}


@pytest.fixture
def client_dtv():
    """Fixture for a client device."""
    mocked_dtv = MockDirectvClass('mock_ip')
    mocked_dtv.attributes = RECORDING
    mocked_dtv._standby = False
    return mocked_dtv


@pytest.fixture
def main_dtv():
    """Fixture for main DVR."""
    return MockDirectvClass('mock_ip')


@pytest.fixture
def dtv_side_effect(client_dtv, main_dtv):
    """Fixture to create DIRECTV instance for main and client."""
    def mock_dtv(ip, port, client_addr):
        if client_addr != '0':
            mocked_dtv = client_dtv
        else:
            mocked_dtv = main_dtv
        mocked_dtv._host = ip
        mocked_dtv._port = port
        mocked_dtv._device = client_addr
        return mocked_dtv
    return mock_dtv


@pytest.fixture
def mock_now():
    """Fixture for dtutil.now."""
    return dt_util.utcnow()


@pytest.fixture
def platforms(hass, dtv_side_effect, mock_now):
    """Fixture for setting up test platforms."""
    config = {
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
        }]
    }

    with MockDependency('DirectPy'), \
            patch('DirectPy.DIRECTV', side_effect=dtv_side_effect), \
            patch('homeassistant.util.dt.utcnow', return_value=mock_now):
        hass.loop.run_until_complete(async_setup_component(
            hass, mp.DOMAIN, config))
        hass.loop.run_until_complete(hass.async_block_till_done())
        yield


async def async_turn_on(hass, entity_id=None):
    """Turn on specified media player or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data)


async def async_turn_off(hass, entity_id=None):
    """Turn off specified media player or all."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data)


async def async_media_pause(hass, entity_id=None):
    """Send the media player the command for pause."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_MEDIA_PAUSE, data)


async def async_media_play(hass, entity_id=None):
    """Send the media player the command for play/pause."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_MEDIA_PLAY, data)


async def async_media_stop(hass, entity_id=None):
    """Send the media player the command for stop."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_MEDIA_STOP, data)


async def async_media_next_track(hass, entity_id=None):
    """Send the media player the command for next track."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_MEDIA_NEXT_TRACK, data)


async def async_media_previous_track(hass, entity_id=None):
    """Send the media player the command for prev track."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    await hass.services.async_call(DOMAIN, SERVICE_MEDIA_PREVIOUS_TRACK, data)


async def async_play_media(hass, media_type, media_id, entity_id=None,
                           enqueue=None):
    """Send the media player the command for playing media."""
    data = {ATTR_MEDIA_CONTENT_TYPE: media_type,
            ATTR_MEDIA_CONTENT_ID: media_id}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    if enqueue:
        data[ATTR_MEDIA_ENQUEUE] = enqueue

    await hass.services.async_call(DOMAIN, SERVICE_PLAY_MEDIA, data)


class MockDirectvClass:
    """A fake DirecTV DVR device."""

    def __init__(self, ip, port=8080, clientAddr='0'):
        """Initialize the fake DirecTV device."""
        self._host = ip
        self._port = port
        self._device = clientAddr
        self._standby = True
        self._play = False

        self._locations = LOCATIONS

        self.attributes = LIVE

    def get_locations(self):
        """Mock for get_locations method."""
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
        return self._standby

    def get_tuned(self):
        """Mock for get_tuned method."""
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
        self.attributes['major'] = int(source)


async def test_setup_platform_config(hass):
    """Test setting up the platform from configuration."""
    with MockDependency('DirectPy'), \
            patch('DirectPy.DIRECTV', new=MockDirectvClass):

        await async_setup_component(hass, mp.DOMAIN, WORKING_CONFIG)
        await hass.async_block_till_done()

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state
    assert len(hass.states.async_entity_ids('media_player')) == 1


async def test_setup_platform_discover(hass):
    """Test setting up the platform from discovery."""
    with MockDependency('DirectPy'), \
            patch('DirectPy.DIRECTV', new=MockDirectvClass):

        hass.async_create_task(
            async_load_platform(hass, mp.DOMAIN, 'directv', DISCOVERY_INFO,
                                {'media_player': {}})
        )
        await hass.async_block_till_done()

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state
    assert len(hass.states.async_entity_ids('media_player')) == 1


async def test_setup_platform_discover_duplicate(hass):
    """Test setting up the platform from discovery."""
    with MockDependency('DirectPy'), \
            patch('DirectPy.DIRECTV', new=MockDirectvClass):

        await async_setup_component(hass, mp.DOMAIN, WORKING_CONFIG)
        await hass.async_block_till_done()
        hass.async_create_task(
            async_load_platform(hass, mp.DOMAIN, 'directv', DISCOVERY_INFO,
                                {'media_player': {}})
        )
        await hass.async_block_till_done()

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state
    assert len(hass.states.async_entity_ids('media_player')) == 1


async def test_setup_platform_discover_client(hass):
    """Test setting up the platform from discovery."""
    LOCATIONS.append({
        'locationName': 'Client 1',
        'clientAddr': '1'
    })
    LOCATIONS.append({
        'locationName': 'Client 2',
        'clientAddr': '2'
    })

    with MockDependency('DirectPy'), \
            patch('DirectPy.DIRECTV', new=MockDirectvClass):

        await async_setup_component(hass, mp.DOMAIN, WORKING_CONFIG)
        await hass.async_block_till_done()

        hass.async_create_task(
            async_load_platform(hass, mp.DOMAIN, 'directv', DISCOVERY_INFO,
                                {'media_player': {}})
        )
        await hass.async_block_till_done()

    del LOCATIONS[-1]
    del LOCATIONS[-1]
    state = hass.states.get(MAIN_ENTITY_ID)
    assert state
    state = hass.states.get('media_player.client_1')
    assert state
    state = hass.states.get('media_player.client_2')
    assert state

    assert len(hass.states.async_entity_ids('media_player')) == 3


async def test_supported_features(hass, platforms):
    """Test supported features."""
    # Features supported for main DVR
    state = hass.states.get(MAIN_ENTITY_ID)
    assert mp.SUPPORT_PAUSE | mp.SUPPORT_TURN_ON | mp.SUPPORT_TURN_OFF |\
        mp.SUPPORT_PLAY_MEDIA | mp.SUPPORT_STOP | mp.SUPPORT_NEXT_TRACK |\
        mp.SUPPORT_PREVIOUS_TRACK | mp.SUPPORT_PLAY ==\
        state.attributes.get('supported_features')

    # Feature supported for clients.
    state = hass.states.get(CLIENT_ENTITY_ID)
    assert mp.SUPPORT_PAUSE |\
        mp.SUPPORT_PLAY_MEDIA | mp.SUPPORT_STOP | mp.SUPPORT_NEXT_TRACK |\
        mp.SUPPORT_PREVIOUS_TRACK | mp.SUPPORT_PLAY ==\
        state.attributes.get('supported_features')


async def test_check_attributes(hass, platforms, mock_now):
    """Test attributes."""
    next_update = mock_now + timedelta(minutes=5)
    with patch('homeassistant.util.dt.utcnow', return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    # Start playing TV
    with patch('homeassistant.util.dt.utcnow',
               return_value=next_update):
        await async_media_play(hass, CLIENT_ENTITY_ID)
        await hass.async_block_till_done()

    state = hass.states.get(CLIENT_ENTITY_ID)
    assert state.state == STATE_PLAYING

    assert state.attributes.get(mp.ATTR_MEDIA_CONTENT_ID) == \
        RECORDING['programId']
    assert state.attributes.get(mp.ATTR_MEDIA_CONTENT_TYPE) == \
        mp.MEDIA_TYPE_TVSHOW
    assert state.attributes.get(mp.ATTR_MEDIA_DURATION) == \
        RECORDING['duration']
    assert state.attributes.get(mp.ATTR_MEDIA_POSITION) == 2
    assert state.attributes.get(
        mp.ATTR_MEDIA_POSITION_UPDATED_AT) == next_update
    assert state.attributes.get(mp.ATTR_MEDIA_TITLE) == RECORDING['title']
    assert state.attributes.get(mp.ATTR_MEDIA_SERIES_TITLE) == \
        RECORDING['episodeTitle']
    assert state.attributes.get(mp.ATTR_MEDIA_CHANNEL) == \
        "{} ({})".format(RECORDING['callsign'], RECORDING['major'])
    assert state.attributes.get(mp.ATTR_INPUT_SOURCE) == RECORDING['major']
    assert state.attributes.get(ATTR_MEDIA_CURRENTLY_RECORDING) == \
        RECORDING['isRecording']
    assert state.attributes.get(ATTR_MEDIA_RATING) == RECORDING['rating']
    assert state.attributes.get(ATTR_MEDIA_RECORDED)
    assert state.attributes.get(ATTR_MEDIA_START_TIME) == \
        datetime(2018, 11, 10, 19, 0, tzinfo=dt_util.UTC)

    # Test to make sure that ATTR_MEDIA_POSITION_UPDATED_AT is not
    # updated if TV is paused.
    with patch('homeassistant.util.dt.utcnow',
               return_value=next_update + timedelta(minutes=5)):
        await async_media_pause(hass, CLIENT_ENTITY_ID)
        await hass.async_block_till_done()

    state = hass.states.get(CLIENT_ENTITY_ID)
    assert state.state == STATE_PAUSED
    assert state.attributes.get(
        mp.ATTR_MEDIA_POSITION_UPDATED_AT) == next_update


async def test_main_services(hass, platforms, main_dtv, mock_now):
    """Test the different services."""
    next_update = mock_now + timedelta(minutes=5)
    with patch('homeassistant.util.dt.utcnow', return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()
    # DVR starts in off state.
    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_OFF

    # All these should call key_press in our class.
    with patch.object(main_dtv, 'key_press',
                      wraps=main_dtv.key_press) as mock_key_press, \
        patch.object(main_dtv, 'tune_channel',
                     wraps=main_dtv.tune_channel) as mock_tune_channel, \
        patch.object(main_dtv, 'get_tuned',
                     wraps=main_dtv.get_tuned) as mock_get_tuned, \
        patch.object(main_dtv, 'get_standby',
                     wraps=main_dtv.get_standby) as mock_get_standby:

        # Turn main DVR on. When turning on DVR is playing.
        await async_turn_on(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        assert mock_key_press.called
        assert mock_key_press.call_args == call('poweron')
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.state == STATE_PLAYING

        # Pause live TV.
        await async_media_pause(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        assert mock_key_press.called
        assert mock_key_press.call_args == call('pause')
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.state == STATE_PAUSED

        # Start play again for live TV.
        await async_media_play(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        assert mock_key_press.called
        assert mock_key_press.call_args == call('play')
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.state == STATE_PLAYING

        # Change channel, currently it should be 202
        assert state.attributes.get('source') == 202
        await async_play_media(hass, 'channel', 7, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        assert mock_tune_channel.called
        assert mock_tune_channel.call_args == call('7')
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.attributes.get('source') == 7

        # Stop live TV.
        await async_media_stop(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        assert mock_key_press.called
        assert mock_key_press.call_args == call('stop')
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.state == STATE_PAUSED

        # Turn main DVR off.
        await async_turn_off(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        assert mock_key_press.called
        assert mock_key_press.call_args == call('poweroff')
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.state == STATE_OFF

        # There should have been 6 calls to check if DVR is in standby
        assert main_dtv.get_standby.call_count == 6
        assert mock_get_standby.call_count == 6
        # There should be 5 calls to get current info (only 1 time it will
        # not be called as DVR is in standby.)
        assert main_dtv.get_tuned.call_count == 5
        assert mock_get_tuned.call_count == 5


async def test_available(hass, platforms, main_dtv, mock_now):
    """Test available status."""
    next_update = mock_now + timedelta(minutes=5)
    with patch('homeassistant.util.dt.utcnow', return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    # Confirm service is currently set to available.
    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE

    # Make update fail 1st time
    next_update = next_update + timedelta(minutes=5)
    with patch.object(
            main_dtv, 'get_standby', side_effect=requests.RequestException), \
            patch('homeassistant.util.dt.utcnow', return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE

    # Make update fail 2nd time within 1 minute
    next_update = next_update + timedelta(seconds=30)
    with patch.object(
            main_dtv, 'get_standby', side_effect=requests.RequestException), \
            patch('homeassistant.util.dt.utcnow', return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE

    # Make update fail 3rd time more then a minute after 1st failure
    next_update = next_update + timedelta(minutes=1)
    with patch.object(
            main_dtv, 'get_standby', side_effect=requests.RequestException), \
            patch('homeassistant.util.dt.utcnow', return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()

    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state == STATE_UNAVAILABLE

    # Recheck state, update should work again.
    next_update = next_update + timedelta(minutes=5)
    with patch('homeassistant.util.dt.utcnow', return_value=next_update):
        async_fire_time_changed(hass, next_update)
        await hass.async_block_till_done()
    state = hass.states.get(MAIN_ENTITY_ID)
    assert state.state != STATE_UNAVAILABLE

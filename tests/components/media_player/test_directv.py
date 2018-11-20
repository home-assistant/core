"""The tests for the DirecTV Media player platform."""
from unittest.mock import patch, Mock

from datetime import datetime, timedelta
import logging
import pytest

import homeassistant.components.media_player as mp
from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE, ATTR_MEDIA_CONTENT_ID, ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_ENQUEUE, DOMAIN, SERVICE_PLAY_MEDIA, SERVICE_SELECT_SOURCE)

from homeassistant.components.media_player.directv import (
    ATTR_MEDIA_CURRENTLY_RECORDING, ATTR_MEDIA_RATING, ATTR_MEDIA_RECORDED,
    ATTR_MEDIA_START_TIME, DATA_DIRECTV, DEFAULT_DEVICE, DEFAULT_PORT,
    setup_platform)
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_DEVICE, CONF_HOST, CONF_NAME, CONF_PORT,
    SERVICE_MEDIA_NEXT_TRACK, SERVICE_MEDIA_PAUSE, SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK, SERVICE_MEDIA_STOP, SERVICE_TURN_OFF,
    SERVICE_TURN_ON, STATE_OFF, STATE_PAUSED, STATE_PLAYING)
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from tests.common import MockDependency

CLIENT_ENTITY_ID = 'media_player.client_dvr'
MAIN_ENTITY_ID = 'media_player.main_dvr'
IP_ADDRESS = '127.0.0.1'

DISCOVERY_INFO = {
    'host': IP_ADDRESS,
    'serial': 1234
}

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

LOCATIONS = [
    {
        'locationName': 'Main DVR',
        'clientAddr': DEFAULT_DEVICE
    }
]

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

WORKING_CONFIG = {
    'media_player': {
        'platform': 'directv',
        CONF_HOST: IP_ADDRESS,
        CONF_NAME: 'Main DVR',
        CONF_PORT: DEFAULT_PORT,
        CONF_DEVICE: DEFAULT_DEVICE
    }
}

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def platforms():
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

    async def setup_test_platforms(hass):
        with MockDependency('DirectPy'), \
             patch('DirectPy.DIRECTV', new=mockDIRECTVClass):
            await async_setup_component(hass, mp.DOMAIN, config)
            await hass.async_block_till_done()

        main_media_entity = hass.data['media_player'].get_entity(
            MAIN_ENTITY_ID)

        client_media_entity = hass.data['media_player'].get_entity(
            CLIENT_ENTITY_ID)

        # Set the client so it seems a recording is being watched.
        client_media_entity.dtv.attributes = RECORDING
        # Clients do not support turning on, setting it as client is on here.
        client_media_entity.dtv._standby = False

        main_media_entity.schedule_update_ha_state(True)
        client_media_entity.schedule_update_ha_state(True)
        await hass.async_block_till_done()

        return (main_media_entity, client_media_entity)

    return setup_test_platforms


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


async def async_select_source(hass, source, entity_id=None):
    """Send the media player the command to select input source."""
    data = {ATTR_INPUT_SOURCE: source}

    if entity_id:
        data[ATTR_ENTITY_ID] = entity_id

    await hass.services.async_call(DOMAIN, SERVICE_SELECT_SOURCE, data)


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


async def test_setup_platform_config(hass):
    """Test setting up the platform from configuration."""
    with MockDependency('DirectPy'), \
            patch('DirectPy.DIRECTV', new=mockDIRECTVClass):

        await async_setup_component(hass, mp.DOMAIN, WORKING_CONFIG)
        await hass.async_block_till_done()

    assert len(hass.data[DATA_DIRECTV]) == 1
    assert (IP_ADDRESS, DEFAULT_DEVICE) in hass.data[DATA_DIRECTV]


async def test_setup_platform_discover(hass):
    """Test setting up the platform from discovery."""
    add_entities = Mock()
    with MockDependency('DirectPy'), \
            patch('DirectPy.DIRECTV', new=mockDIRECTVClass):

        setup_platform(hass, {}, add_entities,
                       discovery_info=DISCOVERY_INFO)

    assert len(hass.data[DATA_DIRECTV]) == 1
    assert add_entities.call_count == 1


async def test_setup_platform_discover_duplicate(hass):
    """Test setting up the platform from discovery."""
    add_entities = Mock()

    with MockDependency('DirectPy'), \
            patch('DirectPy.DIRECTV', new=mockDIRECTVClass):

        await async_setup_component(hass, mp.DOMAIN, WORKING_CONFIG)
        await hass.async_block_till_done()

        setup_platform(hass, {}, add_entities,
                       discovery_info=DISCOVERY_INFO)

    assert len(hass.data[DATA_DIRECTV]) == 1
    assert add_entities.call_count == 1


async def test_setup_platform_discover_client(hass):
    """Test setting up the platform from discovery."""
    add_entities = Mock()

    LOCATIONS.append({
        'locationName': 'Client 1',
        'clientAddr': '1'
    })
    LOCATIONS.append({
        'locationName': 'Client 2',
        'clientAddr': '2'
    })

    with MockDependency('DirectPy'), \
            patch('DirectPy.DIRECTV', new=mockDIRECTVClass):

        await async_setup_component(hass, mp.DOMAIN, WORKING_CONFIG)
        await hass.async_block_till_done()

        setup_platform(hass, {}, add_entities,
                       discovery_info=DISCOVERY_INFO)

    del LOCATIONS[-1]
    del LOCATIONS[-1]
    assert len(hass.data[DATA_DIRECTV]) == 3
    assert (IP_ADDRESS, '1') in hass.data[DATA_DIRECTV]
    assert (IP_ADDRESS, '2') in hass.data[DATA_DIRECTV]


async def test_supported_features(hass, platforms):
    """Test supported features."""
    main_media_entity, client_media_entity = await platforms(hass)

    # Features supported for main DVR
    assert mp.SUPPORT_PAUSE | mp.SUPPORT_TURN_ON | mp.SUPPORT_TURN_OFF |\
        mp.SUPPORT_PLAY_MEDIA | mp.SUPPORT_SELECT_SOURCE |\
        mp.SUPPORT_STOP | mp.SUPPORT_NEXT_TRACK |\
        mp.SUPPORT_PREVIOUS_TRACK | mp.SUPPORT_PLAY ==\
        main_media_entity.supported_features

    # Feature supported for clients.
    assert mp.SUPPORT_PAUSE |\
        mp.SUPPORT_PLAY_MEDIA | mp.SUPPORT_SELECT_SOURCE |\
        mp.SUPPORT_STOP | mp.SUPPORT_NEXT_TRACK |\
        mp.SUPPORT_PREVIOUS_TRACK | mp.SUPPORT_PLAY ==\
        client_media_entity.supported_features


async def test_check_attributes(hass, platforms):
    """Test attributes."""
    main_media_entity, client_media_entity = await platforms(hass)
    now = datetime(2018, 11, 19, 20, 0, 0, tzinfo=dt_util.UTC)

    # Start playing TV
    with patch('homeassistant.helpers.condition.dt_util.now',
               return_value=now):
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
    assert state.attributes.get(mp.ATTR_MEDIA_POSITION_UPDATED_AT) == now
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
    with patch('homeassistant.helpers.condition.dt_util.now',
               return_value=now + timedelta(minutes=5)):
        await async_media_pause(hass, CLIENT_ENTITY_ID)
        await hass.async_block_till_done()

    state = hass.states.get(CLIENT_ENTITY_ID)
    assert state.state == STATE_PAUSED
    assert state.attributes.get(mp.ATTR_MEDIA_POSITION_UPDATED_AT) == now


async def test_main_services(hass, platforms):
    """Test the different services."""
    main_media_entity, client_media_entity = await platforms(hass)

    dtv_inst = main_media_entity.dtv

    # DVR starts in turned off state.
    state = hass.states.get(MAIN_ENTITY_ID)
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
        await async_turn_on(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        mock_key_press.assert_called_with('poweron')
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.state == STATE_PLAYING

        # Pause live TV.
        await async_media_pause(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        mock_key_press.assert_called_with('pause')
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.state == STATE_PAUSED

        # Start play again for live TV.
        await async_media_play(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        mock_key_press.assert_called_with('play')
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.state == STATE_PLAYING

        # Change channel, currently it should be 202
        assert state.attributes.get('source') == 202
        await async_select_source(hass, 7, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        mock_tune_channel.assert_called_with('7')
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.attributes.get('source') == 7

        # Stop live TV.
        await async_media_stop(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        mock_key_press.assert_called_with('stop')
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.state == STATE_PAUSED

        # Turn main DVR off.
        await async_turn_off(hass, MAIN_ENTITY_ID)
        await hass.async_block_till_done()
        mock_key_press.assert_called_with('poweroff')
        state = hass.states.get(MAIN_ENTITY_ID)
        assert state.state == STATE_OFF

        # There should have been 6 calls to check if DVR is in standby
        assert 6 == mock_get_standby.call_count
        # There should be 5 calls to get current info (only 1 time it will
        # not be called as DVR is in standby.)
        assert 5 == mock_get_tuned.call_count


async def test_available(hass, platforms):
    """Test available status."""
    main_media_entity, client_media_entity = await platforms(hass)

    # Confirm service is currently set to available.
    assert main_media_entity.available

    # Make update fail (i.e. DVR offline)
    dtv = main_media_entity.dtv
    main_media_entity.dtv = None
    main_media_entity.schedule_update_ha_state(True)
    await hass.async_block_till_done()
    assert not main_media_entity.available

    # Make update work again (i.e. DVR back online)
    main_media_entity.dtv = dtv
    main_media_entity.schedule_update_ha_state(True)
    await hass.async_block_till_done()
    assert main_media_entity.available

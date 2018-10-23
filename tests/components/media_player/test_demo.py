"""The tests for the Demo Media player platform."""
import unittest
from unittest.mock import patch
import asyncio

from homeassistant.setup import setup_component
from homeassistant.const import HTTP_HEADER_HA_AUTH
import homeassistant.components.media_player as mp
import homeassistant.components.http as http
from homeassistant.helpers.aiohttp_client import DATA_CLIENTSESSION

import requests

from tests.common import get_test_home_assistant, get_test_instance_port
from tests.components.media_player import common

SERVER_PORT = get_test_instance_port()
HTTP_BASE_URL = 'http://127.0.0.1:{}'.format(SERVER_PORT)
API_PASSWORD = "test1234"
HA_HEADERS = {HTTP_HEADER_HA_AUTH: API_PASSWORD}

entity_id = 'media_player.walkman'


class TestDemoMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Shut down test instance."""
        self.hass.stop()

    def test_source_select(self):
        """Test the input source service."""
        entity_id = 'media_player.lounge_room'

        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        state = self.hass.states.get(entity_id)
        assert 'dvd' == state.attributes.get('source')

        common.select_source(self.hass, None, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 'dvd' == state.attributes.get('source')

        common.select_source(self.hass, 'xbox', entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 'xbox' == state.attributes.get('source')

    def test_clear_playlist(self):
        """Test clear playlist."""
        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        assert self.hass.states.is_state(entity_id, 'playing')

        common.clear_playlist(self.hass, entity_id)
        self.hass.block_till_done()
        assert self.hass.states.is_state(entity_id, 'off')

    def test_volume_services(self):
        """Test the volume service."""
        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        state = self.hass.states.get(entity_id)
        assert 1.0 == state.attributes.get('volume_level')

        common.set_volume_level(self.hass, None, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 1.0 == state.attributes.get('volume_level')

        common.set_volume_level(self.hass, 0.5, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 0.5 == state.attributes.get('volume_level')

        common.volume_down(self.hass, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 0.4 == state.attributes.get('volume_level')

        common.volume_up(self.hass, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 0.5 == state.attributes.get('volume_level')

        assert False is state.attributes.get('is_volume_muted')

        common.mute_volume(self.hass, None, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert False is state.attributes.get('is_volume_muted')

        common.mute_volume(self.hass, True, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert True is state.attributes.get('is_volume_muted')

    def test_turning_off_and_on(self):
        """Test turn_on and turn_off."""
        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        assert self.hass.states.is_state(entity_id, 'playing')

        common.turn_off(self.hass, entity_id)
        self.hass.block_till_done()
        assert self.hass.states.is_state(entity_id, 'off')
        assert not mp.is_on(self.hass, entity_id)

        common.turn_on(self.hass, entity_id)
        self.hass.block_till_done()
        assert self.hass.states.is_state(entity_id, 'playing')

        common.toggle(self.hass, entity_id)
        self.hass.block_till_done()
        assert self.hass.states.is_state(entity_id, 'off')
        assert not mp.is_on(self.hass, entity_id)

    def test_playing_pausing(self):
        """Test media_pause."""
        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        assert self.hass.states.is_state(entity_id, 'playing')

        common.media_pause(self.hass, entity_id)
        self.hass.block_till_done()
        assert self.hass.states.is_state(entity_id, 'paused')

        common.media_play_pause(self.hass, entity_id)
        self.hass.block_till_done()
        assert self.hass.states.is_state(entity_id, 'playing')

        common.media_play_pause(self.hass, entity_id)
        self.hass.block_till_done()
        assert self.hass.states.is_state(entity_id, 'paused')

        common.media_play(self.hass, entity_id)
        self.hass.block_till_done()
        assert self.hass.states.is_state(entity_id, 'playing')

    def test_prev_next_track(self):
        """Test media_next_track and media_previous_track ."""
        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        state = self.hass.states.get(entity_id)
        assert 1 == state.attributes.get('media_track')

        common.media_next_track(self.hass, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 2 == state.attributes.get('media_track')

        common.media_next_track(self.hass, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 3 == state.attributes.get('media_track')

        common.media_previous_track(self.hass, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 2 == state.attributes.get('media_track')

        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        ent_id = 'media_player.lounge_room'
        state = self.hass.states.get(ent_id)
        assert 1 == state.attributes.get('media_episode')

        common.media_next_track(self.hass, ent_id)
        self.hass.block_till_done()
        state = self.hass.states.get(ent_id)
        assert 2 == state.attributes.get('media_episode')

        common.media_previous_track(self.hass, ent_id)
        self.hass.block_till_done()
        state = self.hass.states.get(ent_id)
        assert 1 == state.attributes.get('media_episode')

    @patch('homeassistant.components.media_player.demo.DemoYoutubePlayer.'
           'media_seek', autospec=True)
    def test_play_media(self, mock_seek):
        """Test play_media ."""
        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        ent_id = 'media_player.living_room'
        state = self.hass.states.get(ent_id)
        assert 0 < (mp.SUPPORT_PLAY_MEDIA &
                    state.attributes.get('supported_features'))
        assert state.attributes.get('media_content_id') is not None

        common.play_media(self.hass, None, 'some_id', ent_id)
        self.hass.block_till_done()
        state = self.hass.states.get(ent_id)
        assert 0 < (mp.SUPPORT_PLAY_MEDIA &
                    state.attributes.get('supported_features'))
        assert not 'some_id' == state.attributes.get('media_content_id')

        common.play_media(self.hass, 'youtube', 'some_id', ent_id)
        self.hass.block_till_done()
        state = self.hass.states.get(ent_id)
        assert 0 < (mp.SUPPORT_PLAY_MEDIA &
                    state.attributes.get('supported_features'))
        assert 'some_id' == state.attributes.get('media_content_id')

        assert not mock_seek.called
        common.media_seek(self.hass, None, ent_id)
        self.hass.block_till_done()
        assert not mock_seek.called
        common.media_seek(self.hass, 100, ent_id)
        self.hass.block_till_done()
        assert mock_seek.called


class TestMediaPlayerWeb(unittest.TestCase):
    """Test the media player web views sensor."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        assert setup_component(self.hass, http.DOMAIN, {
            http.DOMAIN: {
                http.CONF_SERVER_PORT: SERVER_PORT,
                http.CONF_API_PASSWORD: API_PASSWORD,
            },
        })

        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})

        self.hass.start()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_media_image_proxy(self):
        """Test the media server image proxy server ."""
        fake_picture_data = 'test.test'

        class MockResponse():
            def __init__(self):
                self.status = 200
                self.headers = {'Content-Type': 'sometype'}

            @asyncio.coroutine
            def read(self):
                return fake_picture_data.encode('ascii')

            @asyncio.coroutine
            def release(self):
                pass

        class MockWebsession():

            @asyncio.coroutine
            def get(self, url):
                return MockResponse()

            def detach(self):
                pass

        self.hass.data[DATA_CLIENTSESSION] = MockWebsession()

        assert self.hass.states.is_state(entity_id, 'playing')
        state = self.hass.states.get(entity_id)
        req = requests.get(HTTP_BASE_URL +
                           state.attributes.get('entity_picture'))
        assert req.status_code == 200
        assert req.text == fake_picture_data

"""The tests for the Demo Media player platform."""
import unittest
from unittest.mock import patch

from homeassistant.bootstrap import setup_component
from homeassistant.const import HTTP_HEADER_HA_AUTH
import homeassistant.components.media_player as mp
import homeassistant.components.http as http

import requests
import requests_mock
import time

from tests.common import get_test_home_assistant, get_test_instance_port

SERVER_PORT = get_test_instance_port()
HTTP_BASE_URL = 'http://127.0.0.1:{}'.format(SERVER_PORT)
API_PASSWORD = "test1234"
HA_HEADERS = {HTTP_HEADER_HA_AUTH: API_PASSWORD}

hass = None

entity_id = 'media_player.walkman'


def setUpModule():   # pylint: disable=invalid-name
    """Initalize a Home Assistant server."""
    global hass

    hass = get_test_home_assistant()
    setup_component(hass, http.DOMAIN, {
        http.DOMAIN: {
            http.CONF_SERVER_PORT: SERVER_PORT,
            http.CONF_API_PASSWORD: API_PASSWORD,
        },
    })

    hass.start()
    time.sleep(0.05)


def tearDownModule():   # pylint: disable=invalid-name
    """Stop the Home Assistant server."""
    hass.stop()


class TestDemoMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = hass
        try:
            self.hass.config.components.remove(mp.DOMAIN)
        except ValueError:
            pass

    def test_source_select(self):
        """Test the input source service."""

        entity_id = 'media_player.lounge_room'

        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        state = self.hass.states.get(entity_id)
        assert 'dvd' == state.attributes.get('source')

        mp.select_source(self.hass, None, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 'dvd' == state.attributes.get('source')

        mp.select_source(self.hass, 'xbox', entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 'xbox' == state.attributes.get('source')

    def test_clear_playlist(self):
        """Test clear playlist."""
        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        assert self.hass.states.is_state(entity_id, 'playing')

        mp.clear_playlist(self.hass, entity_id)
        self.hass.block_till_done()
        assert self.hass.states.is_state(entity_id, 'off')

    def test_volume_services(self):
        """Test the volume service."""
        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        state = self.hass.states.get(entity_id)
        print(state)
        assert 1.0 == state.attributes.get('volume_level')

        mp.set_volume_level(self.hass, None, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 1.0 == state.attributes.get('volume_level')

        mp.set_volume_level(self.hass, 0.5, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 0.5 == state.attributes.get('volume_level')

        mp.volume_down(self.hass, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 0.4 == state.attributes.get('volume_level')

        mp.volume_up(self.hass, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 0.5 == state.attributes.get('volume_level')

        assert False is state.attributes.get('is_volume_muted')

        mp.mute_volume(self.hass, None, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert False is state.attributes.get('is_volume_muted')

        mp.mute_volume(self.hass, True, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert True is state.attributes.get('is_volume_muted')

    def test_turning_off_and_on(self):
        """Test turn_on and turn_off."""
        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        assert self.hass.states.is_state(entity_id, 'playing')

        mp.turn_off(self.hass, entity_id)
        self.hass.block_till_done()
        assert self.hass.states.is_state(entity_id, 'off')
        assert not mp.is_on(self.hass, entity_id)

        mp.turn_on(self.hass, entity_id)
        self.hass.block_till_done()
        assert self.hass.states.is_state(entity_id, 'playing')

        mp.toggle(self.hass, entity_id)
        self.hass.block_till_done()
        assert self.hass.states.is_state(entity_id, 'off')
        assert not mp.is_on(self.hass, entity_id)

    def test_playing_pausing(self):
        """Test media_pause."""
        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        assert self.hass.states.is_state(entity_id, 'playing')

        mp.media_pause(self.hass, entity_id)
        self.hass.block_till_done()
        assert self.hass.states.is_state(entity_id, 'paused')

        mp.media_play_pause(self.hass, entity_id)
        self.hass.block_till_done()
        assert self.hass.states.is_state(entity_id, 'playing')

        mp.media_play_pause(self.hass, entity_id)
        self.hass.block_till_done()
        assert self.hass.states.is_state(entity_id, 'paused')

        mp.media_play(self.hass, entity_id)
        self.hass.block_till_done()
        assert self.hass.states.is_state(entity_id, 'playing')

    def test_prev_next_track(self):
        """Test media_next_track and media_previous_track ."""
        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        state = self.hass.states.get(entity_id)
        assert 1 == state.attributes.get('media_track')
        assert 0 == (mp.SUPPORT_PREVIOUS_TRACK &
                     state.attributes.get('supported_media_commands'))

        mp.media_next_track(self.hass, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 2 == state.attributes.get('media_track')
        assert 0 < (mp.SUPPORT_PREVIOUS_TRACK &
                    state.attributes.get('supported_media_commands'))

        mp.media_next_track(self.hass, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 3 == state.attributes.get('media_track')
        assert 0 < (mp.SUPPORT_PREVIOUS_TRACK &
                    state.attributes.get('supported_media_commands'))

        mp.media_previous_track(self.hass, entity_id)
        self.hass.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 2 == state.attributes.get('media_track')
        assert 0 < (mp.SUPPORT_PREVIOUS_TRACK &
                    state.attributes.get('supported_media_commands'))

        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        ent_id = 'media_player.lounge_room'
        state = self.hass.states.get(ent_id)
        assert 1 == state.attributes.get('media_episode')
        assert 0 == (mp.SUPPORT_PREVIOUS_TRACK &
                     state.attributes.get('supported_media_commands'))

        mp.media_next_track(self.hass, ent_id)
        self.hass.block_till_done()
        state = self.hass.states.get(ent_id)
        assert 2 == state.attributes.get('media_episode')
        assert 0 < (mp.SUPPORT_PREVIOUS_TRACK &
                    state.attributes.get('supported_media_commands'))

        mp.media_previous_track(self.hass, ent_id)
        self.hass.block_till_done()
        state = self.hass.states.get(ent_id)
        assert 1 == state.attributes.get('media_episode')
        assert 0 == (mp.SUPPORT_PREVIOUS_TRACK &
                     state.attributes.get('supported_media_commands'))

    @requests_mock.Mocker(real_http=True)
    def test_media_image_proxy(self, m):
        """Test the media server image proxy server ."""
        fake_picture_data = 'test.test'
        m.get('https://graph.facebook.com/v2.5/107771475912710/'
              'picture?type=large', text=fake_picture_data)
        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        assert self.hass.states.is_state(entity_id, 'playing')
        state = self.hass.states.get(entity_id)
        req = requests.get(HTTP_BASE_URL +
                           state.attributes.get('entity_picture'))
        assert req.text == fake_picture_data

    @patch('homeassistant.components.media_player.demo.DemoYoutubePlayer.'
           'media_seek')
    def test_play_media(self, mock_seek):
        """Test play_media ."""
        assert setup_component(
            self.hass, mp.DOMAIN,
            {'media_player': {'platform': 'demo'}})
        ent_id = 'media_player.living_room'
        state = self.hass.states.get(ent_id)
        assert 0 < (mp.SUPPORT_PLAY_MEDIA &
                    state.attributes.get('supported_media_commands'))
        assert state.attributes.get('media_content_id') is not None

        mp.play_media(self.hass, None, 'some_id', ent_id)
        self.hass.block_till_done()
        state = self.hass.states.get(ent_id)
        assert 0 < (mp.SUPPORT_PLAY_MEDIA &
                    state.attributes.get('supported_media_commands'))
        assert not 'some_id' == state.attributes.get('media_content_id')

        mp.play_media(self.hass, 'youtube', 'some_id', ent_id)
        self.hass.block_till_done()
        state = self.hass.states.get(ent_id)
        assert 0 < (mp.SUPPORT_PLAY_MEDIA &
                    state.attributes.get('supported_media_commands'))
        assert 'some_id' == state.attributes.get('media_content_id')

        assert not mock_seek.called
        mp.media_seek(self.hass, None, ent_id)
        self.hass.block_till_done()
        assert not mock_seek.called
        mp.media_seek(self.hass, 100, ent_id)
        self.hass.block_till_done()
        assert mock_seek.called

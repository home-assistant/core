"""
tests.component.media_player.test_demo
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests demo media_player component.
"""
import unittest
from unittest.mock import patch
import homeassistant.components.media_player as mp

from tests.common import get_test_home_assistant

entity_id = 'media_player.walkman'


class TestDemoMediaPlayer(unittest.TestCase):
    """ Test the media_player module. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_volume_services(self):
        assert mp.setup(self.hass, {'media_player': {'platform': 'demo'}})
        state = self.hass.states.get(entity_id)
        assert 1.0 == state.attributes.get('volume_level')

        mp.set_volume_level(self.hass, 0.5, entity_id)
        self.hass.pool.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 0.5 == state.attributes.get('volume_level')

        mp.volume_down(self.hass, entity_id)
        self.hass.pool.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 0.4 == state.attributes.get('volume_level')

        mp.volume_up(self.hass, entity_id)
        self.hass.pool.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 0.5 == state.attributes.get('volume_level')

        assert False is state.attributes.get('is_volume_muted')
        mp.mute_volume(self.hass, True, entity_id)
        self.hass.pool.block_till_done()
        state = self.hass.states.get(entity_id)
        assert True is state.attributes.get('is_volume_muted')

    def test_turning_off_and_on(self):
        assert mp.setup(self.hass, {'media_player': {'platform': 'demo'}})
        assert self.hass.states.is_state(entity_id, 'playing')

        mp.turn_off(self.hass, entity_id)
        self.hass.pool.block_till_done()
        assert self.hass.states.is_state(entity_id, 'off')
        assert not mp.is_on(self.hass, entity_id)

        mp.turn_on(self.hass, entity_id)
        self.hass.pool.block_till_done()
        assert self.hass.states.is_state(entity_id, 'playing')

        mp.toggle(self.hass, entity_id)
        self.hass.pool.block_till_done()
        assert self.hass.states.is_state(entity_id, 'off')
        assert not mp.is_on(self.hass, entity_id)

    def test_playing_pausing(self):
        assert mp.setup(self.hass, {'media_player': {'platform': 'demo'}})
        assert self.hass.states.is_state(entity_id, 'playing')

        mp.media_pause(self.hass, entity_id)
        self.hass.pool.block_till_done()
        assert self.hass.states.is_state(entity_id, 'paused')

        mp.media_play_pause(self.hass, entity_id)
        self.hass.pool.block_till_done()
        assert self.hass.states.is_state(entity_id, 'playing')

        mp.media_play_pause(self.hass, entity_id)
        self.hass.pool.block_till_done()
        assert self.hass.states.is_state(entity_id, 'paused')

        mp.media_play(self.hass, entity_id)
        self.hass.pool.block_till_done()
        assert self.hass.states.is_state(entity_id, 'playing')

    def test_prev_next_track(self):
        assert mp.setup(self.hass, {'media_player': {'platform': 'demo'}})
        state = self.hass.states.get(entity_id)
        assert 1 == state.attributes.get('media_track')
        assert 0 == (mp.SUPPORT_PREVIOUS_TRACK &
                     state.attributes.get('supported_media_commands'))

        mp.media_next_track(self.hass, entity_id)
        self.hass.pool.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 2 == state.attributes.get('media_track')
        assert 0 < (mp.SUPPORT_PREVIOUS_TRACK &
                    state.attributes.get('supported_media_commands'))

        mp.media_next_track(self.hass, entity_id)
        self.hass.pool.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 3 == state.attributes.get('media_track')
        assert 0 < (mp.SUPPORT_PREVIOUS_TRACK &
                    state.attributes.get('supported_media_commands'))

        mp.media_previous_track(self.hass, entity_id)
        self.hass.pool.block_till_done()
        state = self.hass.states.get(entity_id)
        assert 2 == state.attributes.get('media_track')
        assert 0 < (mp.SUPPORT_PREVIOUS_TRACK &
                    state.attributes.get('supported_media_commands'))

    @patch('homeassistant.components.media_player.demo.DemoYoutubePlayer.'
           'media_seek')
    def test_play_media(self, mock_seek):
        assert mp.setup(self.hass, {'media_player': {'platform': 'demo'}})
        ent_id = 'media_player.living_room'
        state = self.hass.states.get(ent_id)
        assert 0 < (mp.SUPPORT_PLAY_MEDIA &
                    state.attributes.get('supported_media_commands'))
        assert state.attributes.get('media_content_id') is not None

        mp.play_media(self.hass, 'youtube', 'some_id', ent_id)
        self.hass.pool.block_till_done()
        state = self.hass.states.get(ent_id)
        assert 0 < (mp.SUPPORT_PLAY_MEDIA &
                    state.attributes.get('supported_media_commands'))
        assert 'some_id' == state.attributes.get('media_content_id')

        assert not mock_seek.called
        mp.media_seek(self.hass, 100, ent_id)
        self.hass.pool.block_till_done()
        assert mock_seek.called

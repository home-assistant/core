"""
tests.component.media_player.test_universal
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests universal media_player component.
"""
from copy import copy
import unittest

import homeassistant.core as ha
from homeassistant.const import (
    STATE_OFF, STATE_ON, STATE_UNKNOWN, STATE_PLAYING, STATE_PAUSED)
import homeassistant.components.switch as switch
import homeassistant.components.media_player as media_player
import homeassistant.components.media_player.universal as universal


class MockMediaPlayer(media_player.MediaPlayerDevice):
    """ Mock media player for testing """

    def __init__(self, hass, name):
        self.hass = hass
        self._name = name
        self.entity_id = media_player.ENTITY_ID_FORMAT.format(name)
        self._state = STATE_OFF
        self._volume_level = 0
        self._is_volume_muted = False
        self._media_title = None
        self._supported_media_commands = 0

    @property
    def name(self):
        """ name of player """
        return self._name

    @property
    def state(self):
        """ state of the player """
        return self._state

    @property
    def volume_level(self):
        """ volume level of player """
        return self._volume_level

    @property
    def is_volume_muted(self):
        """ if the media player is muted """
        return self._is_volume_muted

    @property
    def supported_media_commands(self):
        """ supported media commands flag """
        return self._supported_media_commands

    def turn_on(self):
        """ mock turn_on function """
        self._state = STATE_UNKNOWN

    def turn_off(self):
        """ mock turn_off function """
        self._state = STATE_OFF

    def mute_volume(self):
        """ mock mute function """
        self._is_volume_muted = ~self._is_volume_muted

    def set_volume_level(self, volume):
        """ mock set volume level """
        self._volume_level = volume

    def media_play(self):
        """ mock play """
        self._state = STATE_PLAYING

    def media_pause(self):
        """ mock pause """
        self._state = STATE_PAUSED


class TestMediaPlayer(unittest.TestCase):
    """ Test the media_player module. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()

        self.mock_mp_1 = MockMediaPlayer(self.hass, 'mock1')
        self.mock_mp_1.update_ha_state()

        self.mock_mp_2 = MockMediaPlayer(self.hass, 'mock2')
        self.mock_mp_2.update_ha_state()

        self.mock_mute_switch_id = switch.ENTITY_ID_FORMAT.format('mute')
        self.hass.states.set(self.mock_mute_switch_id, STATE_OFF)

        self.mock_state_switch_id = switch.ENTITY_ID_FORMAT.format('state')
        self.hass.states.set(self.mock_state_switch_id, STATE_OFF)

        self.config_children_only = \
            {'name': 'test', 'platform': 'universal',
             'children': [media_player.ENTITY_ID_FORMAT.format('mock1'),
                          media_player.ENTITY_ID_FORMAT.format('mock2')]}
        self.config_children_and_attr = \
            {'name': 'test', 'platform': 'universal',
             'children': [media_player.ENTITY_ID_FORMAT.format('mock1'),
                          media_player.ENTITY_ID_FORMAT.format('mock2')],
             'attributes': {
                 'is_volume_muted': self.mock_mute_switch_id,
                 'state': self.mock_state_switch_id}}

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_check_config_children_only(self):
        """ Check config with only children """
        config_start = copy(self.config_children_only)
        del config_start['platform']
        config_start['commands'] = {}
        config_start['attributes'] = {}

        response = universal.validate_config(self.config_children_only)

        self.assertTrue(response)
        self.assertEqual(config_start, self.config_children_only)

    def test_check_config_children_and_attr(self):
        """ Check config with children and attributes """
        config_start = copy(self.config_children_and_attr)
        del config_start['platform']
        config_start['commands'] = {}

        response = universal.validate_config(self.config_children_and_attr)

        self.assertTrue(response)
        self.assertEqual(config_start, self.config_children_and_attr)

    def test_dependencies(self):
        """ test dependencies property """
        config = self.config_children_and_attr
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        depend = ump.dependencies
        depend.sort()

        check_depend = [media_player.ENTITY_ID_FORMAT.format('mock1'),
                        media_player.ENTITY_ID_FORMAT.format('mock2'),
                        self.mock_mute_switch_id, self.mock_state_switch_id]
        check_depend.sort()

        self.assertEqual(depend, check_depend)

    def test_master_state(self):
        """ test master state property """
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        self.assertEqual(None, ump.master_state)

    def test_master_state_with_attrs(self):
        """ test master state property """
        config = self.config_children_and_attr
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        self.assertEqual(STATE_OFF, ump.master_state)

        self.hass.states.set(self.mock_state_switch_id, STATE_ON)

        self.assertEqual(STATE_ON, ump.master_state)

    def test_master_state_with_bad_attrs(self):
        """ test master state property """
        config = self.config_children_and_attr
        config['attributes']['state'] = 'bad.entity_id'
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        self.assertEqual(STATE_OFF, ump.master_state)

    def test_active_child_state(self):
        """ test active child state property """
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        ump.update_state()

        self.assertEqual(None, ump.active_child_state)

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.update_ha_state()
        ump.update_state()
        self.assertEqual(self.mock_mp_1.entity_id,
                         ump.active_child_state.entity_id)

        self.mock_mp_2._state = STATE_PLAYING
        self.mock_mp_2.update_ha_state()
        ump.update_state()
        self.assertEqual(self.mock_mp_1.entity_id,
                         ump.active_child_state.entity_id)

        self.mock_mp_1._state = STATE_OFF
        self.mock_mp_1.update_ha_state()
        ump.update_state()
        self.assertEqual(self.mock_mp_2.entity_id,
                         ump.active_child_state.entity_id)

    def test_name(self):
        """ test name property """
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        self.assertEqual(config['name'], ump.name)

    def test_state_children_only(self):
        """ test media player state with only children """
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        ump.update_state()

        self.assertTrue(ump.state, STATE_OFF)

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.update_ha_state()
        ump.update_state()
        self.assertEqual(STATE_PLAYING, ump.state)

    def test_state_with_children_and_attrs(self):
        """ test media player with children and master state """
        config = self.config_children_and_attr
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        ump.update_state()

        self.assertEqual(ump.state, STATE_OFF)

        self.hass.states.set(self.mock_state_switch_id, STATE_ON)
        ump.update_state()
        self.assertEqual(ump.state, STATE_ON)

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.update_ha_state()
        ump.update_state()
        self.assertEqual(ump.state, STATE_PLAYING)

        self.hass.states.set(self.mock_state_switch_id, STATE_OFF)
        ump.update_state()
        self.assertEqual(ump.state, STATE_OFF)

    def test_volume_level(self):
        """ test volume level property """
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        ump.update_state()

        self.assertEqual(None, ump.volume_level)

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.update_ha_state()
        ump.update_state()
        self.assertEqual(0, ump.volume_level)

        self.mock_mp_1._volume_level = 1
        self.mock_mp_1.update_ha_state()
        ump.update_state()
        self.assertEqual(1, ump.volume_level)

    def test_is_volume_muted_children_only(self):
        """ test is volume muted property w/ children only """
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        ump.update_state()

        self.assertFalse(ump.is_volume_muted)

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.update_ha_state()
        ump.update_state()
        self.assertFalse(ump.is_volume_muted)

        self.mock_mp_1._is_volume_muted = True
        self.mock_mp_1.update_ha_state()
        ump.update_state()
        self.assertTrue(ump.is_volume_muted)

    def test_is_volume_muted_children_and_attr(self):
        """ test is volume muted property w/ children and attrs """
        config = self.config_children_and_attr
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        self.assertFalse(ump.is_volume_muted)

        self.hass.states.set(self.mock_mute_switch_id, STATE_ON)
        self.assertTrue(ump.is_volume_muted)

    def test_supported_media_commands_children_only(self):
        """ test supported media commands with only children """
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        ump.update_state()

        self.assertEqual(0, ump.supported_media_commands)

        self.mock_mp_1._supported_media_commands = 512
        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.update_ha_state()
        ump.update_state()
        self.assertEqual(512, ump.supported_media_commands)

    def test_supported_media_commands_children_and_cmds(self):
        """ test supported media commands with children and attrs """
        config = self.config_children_and_attr
        universal.validate_config(config)
        config['commands']['turn_on'] = 'test'
        config['commands']['turn_off'] = 'test'
        config['commands']['volume_up'] = 'test'
        config['commands']['volume_down'] = 'test'
        config['commands']['volume_mute'] = 'test'

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        ump.update_state()

        self.mock_mp_1._supported_media_commands = \
            universal.SUPPORT_VOLUME_SET
        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.update_ha_state()
        ump.update_state()

        check_flags = universal.SUPPORT_TURN_ON | universal.SUPPORT_TURN_OFF \
            | universal.SUPPORT_VOLUME_STEP | universal.SUPPORT_VOLUME_MUTE

        self.assertEqual(check_flags, ump.supported_media_commands)

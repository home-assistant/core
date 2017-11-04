"""The tests for the Universal Media player platform."""
from copy import copy
import unittest

from homeassistant.const import (
    STATE_OFF, STATE_ON, STATE_UNKNOWN, STATE_PLAYING, STATE_PAUSED)
import homeassistant.components.switch as switch
import homeassistant.components.input_number as input_number
import homeassistant.components.input_select as input_select
import homeassistant.components.media_player as media_player
import homeassistant.components.media_player.universal as universal
from homeassistant.util.async import run_coroutine_threadsafe

from tests.common import mock_service, get_test_home_assistant


class MockMediaPlayer(media_player.MediaPlayerDevice):
    """Mock media player for testing."""

    def __init__(self, hass, name):
        """Initialize the media player."""
        self.hass = hass
        self._name = name
        self.entity_id = media_player.ENTITY_ID_FORMAT.format(name)
        self._state = STATE_OFF
        self._volume_level = 0
        self._is_volume_muted = False
        self._media_title = None
        self._supported_features = 0
        self._source = None
        self._tracks = 12
        self._media_image_url = None
        self._shuffle = False

        self.service_calls = {
            'turn_on': mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_TURN_ON),
            'turn_off': mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_TURN_OFF),
            'mute_volume': mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_MUTE),
            'set_volume_level': mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_SET),
            'media_play': mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_PLAY),
            'media_pause': mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_PAUSE),
            'media_previous_track': mock_service(
                hass, media_player.DOMAIN,
                media_player.SERVICE_MEDIA_PREVIOUS_TRACK),
            'media_next_track': mock_service(
                hass, media_player.DOMAIN,
                media_player.SERVICE_MEDIA_NEXT_TRACK),
            'media_seek': mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_MEDIA_SEEK),
            'play_media': mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_PLAY_MEDIA),
            'volume_up': mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_UP),
            'volume_down': mock_service(
                hass, media_player.DOMAIN, media_player.SERVICE_VOLUME_DOWN),
            'media_play_pause': mock_service(
                hass, media_player.DOMAIN,
                media_player.SERVICE_MEDIA_PLAY_PAUSE),
            'select_source': mock_service(
                hass, media_player.DOMAIN,
                media_player.SERVICE_SELECT_SOURCE),
            'clear_playlist': mock_service(
                hass, media_player.DOMAIN,
                media_player.SERVICE_CLEAR_PLAYLIST),
            'shuffle_set': mock_service(
                hass, media_player.DOMAIN,
                media_player.SERVICE_SHUFFLE_SET),
        }

    @property
    def name(self):
        """Return the name of player."""
        return self._name

    @property
    def state(self):
        """Return the state of the player."""
        return self._state

    @property
    def volume_level(self):
        """The volume level of player."""
        return self._volume_level

    @property
    def is_volume_muted(self):
        """Return true if the media player is muted."""
        return self._is_volume_muted

    @property
    def supported_features(self):
        """Flag media player features that are supported."""
        return self._supported_features

    @property
    def media_image_url(self):
        """Image url of current playing media."""
        return self._media_image_url

    @property
    def shuffle(self):
        """Return true if the media player is shuffling."""
        return self._shuffle

    def turn_on(self):
        """Mock turn_on function."""
        self._state = STATE_UNKNOWN

    def turn_off(self):
        """Mock turn_off function."""
        self._state = STATE_OFF

    def mute_volume(self):
        """Mock mute function."""
        self._is_volume_muted = ~self._is_volume_muted

    def set_volume_level(self, volume):
        """Mock set volume level."""
        self._volume_level = volume

    def media_play(self):
        """Mock play."""
        self._state = STATE_PLAYING

    def media_pause(self):
        """Mock pause."""
        self._state = STATE_PAUSED

    def select_source(self, source):
        """Set the input source."""
        self._state = source

    def clear_playlist(self):
        """Clear players playlist."""
        self._tracks = 0

    def set_shuffle(self, shuffle):
        """Clear players playlist."""
        self._shuffle = shuffle


class TestMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        self.mock_mp_1 = MockMediaPlayer(self.hass, 'mock1')
        self.mock_mp_1.schedule_update_ha_state()

        self.mock_mp_2 = MockMediaPlayer(self.hass, 'mock2')
        self.mock_mp_2.schedule_update_ha_state()

        self.hass.block_till_done()

        self.mock_mute_switch_id = switch.ENTITY_ID_FORMAT.format('mute')
        self.hass.states.set(self.mock_mute_switch_id, STATE_OFF)

        self.mock_state_switch_id = switch.ENTITY_ID_FORMAT.format('state')
        self.hass.states.set(self.mock_state_switch_id, STATE_OFF)

        self.mock_volume_id = input_number.ENTITY_ID_FORMAT.format(
            'volume_level')
        self.hass.states.set(self.mock_volume_id, 0)

        self.mock_source_list_id = input_select.ENTITY_ID_FORMAT.format(
            'source_list')
        self.hass.states.set(self.mock_source_list_id, ['dvd', 'htpc'])

        self.mock_source_id = input_select.ENTITY_ID_FORMAT.format('source')
        self.hass.states.set(self.mock_source_id, 'dvd')

        self.mock_shuffle_switch_id = switch.ENTITY_ID_FORMAT.format('shuffle')
        self.hass.states.set(self.mock_shuffle_switch_id, STATE_OFF)

        self.config_children_only = {
            'name': 'test', 'platform': 'universal',
            'children': [media_player.ENTITY_ID_FORMAT.format('mock1'),
                         media_player.ENTITY_ID_FORMAT.format('mock2')]
        }
        self.config_children_and_attr = {
            'name': 'test', 'platform': 'universal',
            'children': [media_player.ENTITY_ID_FORMAT.format('mock1'),
                         media_player.ENTITY_ID_FORMAT.format('mock2')],
            'attributes': {
                'is_volume_muted': self.mock_mute_switch_id,
                'volume_level': self.mock_volume_id,
                'source': self.mock_source_id,
                'source_list': self.mock_source_list_id,
                'state': self.mock_state_switch_id,
                'shuffle': self.mock_shuffle_switch_id
            }
        }

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_config_children_only(self):
        """Check config with only children."""
        config_start = copy(self.config_children_only)
        del config_start['platform']
        config_start['commands'] = {}
        config_start['attributes'] = {}

        response = universal.validate_config(self.config_children_only)

        self.assertTrue(response)
        self.assertEqual(config_start, self.config_children_only)

    def test_config_children_and_attr(self):
        """Check config with children and attributes."""
        config_start = copy(self.config_children_and_attr)
        del config_start['platform']
        config_start['commands'] = {}

        response = universal.validate_config(self.config_children_and_attr)

        self.assertTrue(response)
        self.assertEqual(config_start, self.config_children_and_attr)

    def test_config_no_name(self):
        """Check config with no Name entry."""
        response = universal.validate_config({'platform': 'universal'})

        self.assertFalse(response)

    def test_config_bad_children(self):
        """Check config with bad children entry."""
        config_no_children = {'name': 'test', 'platform': 'universal'}
        config_bad_children = {'name': 'test', 'children': {},
                               'platform': 'universal'}

        response = universal.validate_config(config_no_children)
        self.assertTrue(response)
        self.assertEqual([], config_no_children['children'])

        response = universal.validate_config(config_bad_children)
        self.assertTrue(response)
        self.assertEqual([], config_bad_children['children'])

    def test_config_bad_commands(self):
        """Check config with bad commands entry."""
        config = {'name': 'test', 'commands': [], 'platform': 'universal'}

        response = universal.validate_config(config)
        self.assertTrue(response)
        self.assertEqual({}, config['commands'])

    def test_config_bad_attributes(self):
        """Check config with bad attributes."""
        config = {'name': 'test', 'attributes': [], 'platform': 'universal'}

        response = universal.validate_config(config)
        self.assertTrue(response)
        self.assertEqual({}, config['attributes'])

    def test_config_bad_key(self):
        """Check config with bad key."""
        config = {'name': 'test', 'asdf': 5, 'platform': 'universal'}

        response = universal.validate_config(config)
        self.assertTrue(response)
        self.assertFalse('asdf' in config)

    def test_platform_setup(self):
        """Test platform setup."""
        config = {'name': 'test', 'platform': 'universal'}
        bad_config = {'platform': 'universal'}
        entities = []

        def add_devices(new_entities):
            """Add devices to list."""
            for dev in new_entities:
                entities.append(dev)

        run_coroutine_threadsafe(
            universal.async_setup_platform(self.hass, bad_config, add_devices),
            self.hass.loop).result()
        self.assertEqual(0, len(entities))

        run_coroutine_threadsafe(
            universal.async_setup_platform(self.hass, config, add_devices),
            self.hass.loop).result()
        self.assertEqual(1, len(entities))
        self.assertEqual('test', entities[0].name)

    def test_master_state(self):
        """Test master state property."""
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        self.assertEqual(None, ump.master_state)

    def test_master_state_with_attrs(self):
        """Test master state property."""
        config = self.config_children_and_attr
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        self.assertEqual(STATE_OFF, ump.master_state)
        self.hass.states.set(self.mock_state_switch_id, STATE_ON)
        self.assertEqual(STATE_ON, ump.master_state)

    def test_master_state_with_bad_attrs(self):
        """Test master state property."""
        config = self.config_children_and_attr
        config['attributes']['state'] = 'bad.entity_id'
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        self.assertEqual(STATE_OFF, ump.master_state)

    def test_active_child_state(self):
        """Test active child state property."""
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        self.assertEqual(None, ump._child_state)

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        self.assertEqual(self.mock_mp_1.entity_id,
                         ump._child_state.entity_id)

        self.mock_mp_2._state = STATE_PLAYING
        self.mock_mp_2.schedule_update_ha_state()
        self.hass.block_till_done()
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        self.assertEqual(self.mock_mp_1.entity_id,
                         ump._child_state.entity_id)

        self.mock_mp_1._state = STATE_OFF
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        self.assertEqual(self.mock_mp_2.entity_id,
                         ump._child_state.entity_id)

    def test_name(self):
        """Test name property."""
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        self.assertEqual(config['name'], ump.name)

    def test_polling(self):
        """Test should_poll property."""
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        self.assertEqual(False, ump.should_poll)

    def test_state_children_only(self):
        """Test media player state with only children."""
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        self.assertTrue(ump.state, STATE_OFF)

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        self.assertEqual(STATE_PLAYING, ump.state)

    def test_state_with_children_and_attrs(self):
        """Test media player with children and master state."""
        config = self.config_children_and_attr
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        self.assertEqual(STATE_OFF, ump.state)

        self.hass.states.set(self.mock_state_switch_id, STATE_ON)
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        self.assertEqual(STATE_ON, ump.state)

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        self.assertEqual(STATE_PLAYING, ump.state)

        self.hass.states.set(self.mock_state_switch_id, STATE_OFF)
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        self.assertEqual(STATE_OFF, ump.state)

    def test_volume_level(self):
        """Test volume level property."""
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        self.assertEqual(None, ump.volume_level)

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        self.assertEqual(0, ump.volume_level)

        self.mock_mp_1._volume_level = 1
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        self.assertEqual(1, ump.volume_level)

    def test_media_image_url(self):
        """Test media_image_url property."""
        TEST_URL = "test_url"
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        self.assertEqual(None, ump.media_image_url)

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1._media_image_url = TEST_URL
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        # mock_mp_1 will convert the url to the api proxy url. This test
        # ensures ump passes through the same url without an additional proxy.
        self.assertEqual(self.mock_mp_1.entity_picture, ump.entity_picture)

    def test_is_volume_muted_children_only(self):
        """Test is volume muted property w/ children only."""
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        self.assertFalse(ump.is_volume_muted)

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        self.assertFalse(ump.is_volume_muted)

        self.mock_mp_1._is_volume_muted = True
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        self.assertTrue(ump.is_volume_muted)

    def test_source_list_children_and_attr(self):
        """Test source list property w/ children and attrs."""
        config = self.config_children_and_attr
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        self.assertEqual("['dvd', 'htpc']", ump.source_list)

        self.hass.states.set(self.mock_source_list_id, ['dvd', 'htpc', 'game'])
        self.assertEqual("['dvd', 'htpc', 'game']", ump.source_list)

    def test_source_children_and_attr(self):
        """Test source property w/ children and attrs."""
        config = self.config_children_and_attr
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        self.assertEqual('dvd', ump.source)

        self.hass.states.set(self.mock_source_id, 'htpc')
        self.assertEqual('htpc', ump.source)

    def test_volume_level_children_and_attr(self):
        """Test volume level property w/ children and attrs."""
        config = self.config_children_and_attr
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        self.assertEqual('0', ump.volume_level)

        self.hass.states.set(self.mock_volume_id, 100)
        self.assertEqual('100', ump.volume_level)

    def test_is_volume_muted_children_and_attr(self):
        """Test is volume muted property w/ children and attrs."""
        config = self.config_children_and_attr
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)

        self.assertFalse(ump.is_volume_muted)

        self.hass.states.set(self.mock_mute_switch_id, STATE_ON)
        self.assertTrue(ump.is_volume_muted)

    def test_supported_features_children_only(self):
        """Test supported media commands with only children."""
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        self.assertEqual(0, ump.supported_features)

        self.mock_mp_1._supported_features = 512
        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()
        self.assertEqual(512, ump.supported_features)

    def test_supported_features_children_and_cmds(self):
        """Test supported media commands with children and attrs."""
        config = self.config_children_and_attr
        universal.validate_config(config)
        config['commands']['turn_on'] = 'test'
        config['commands']['turn_off'] = 'test'
        config['commands']['volume_up'] = 'test'
        config['commands']['volume_down'] = 'test'
        config['commands']['volume_mute'] = 'test'
        config['commands']['volume_set'] = 'test'
        config['commands']['select_source'] = 'test'
        config['commands']['shuffle_set'] = 'test'

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        self.mock_mp_1._state = STATE_PLAYING
        self.mock_mp_1.schedule_update_ha_state()
        self.hass.block_till_done()
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        check_flags = universal.SUPPORT_TURN_ON | universal.SUPPORT_TURN_OFF \
            | universal.SUPPORT_VOLUME_STEP | universal.SUPPORT_VOLUME_MUTE \
            | universal.SUPPORT_SELECT_SOURCE | universal.SUPPORT_SHUFFLE_SET

        self.assertEqual(check_flags, ump.supported_features)

    def test_service_call_no_active_child(self):
        """Test a service call to children with no active child."""
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        self.mock_mp_1._state = STATE_OFF
        self.mock_mp_1.schedule_update_ha_state()
        self.mock_mp_2._state = STATE_OFF
        self.mock_mp_2.schedule_update_ha_state()
        self.hass.block_till_done()
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        run_coroutine_threadsafe(
            ump.async_turn_off(),
            self.hass.loop).result()
        self.assertEqual(0, len(self.mock_mp_1.service_calls['turn_off']))
        self.assertEqual(0, len(self.mock_mp_2.service_calls['turn_off']))

    def test_service_call_to_child(self):
        """Test service calls that should be routed to a child."""
        config = self.config_children_only
        universal.validate_config(config)

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        self.mock_mp_2._state = STATE_PLAYING
        self.mock_mp_2.schedule_update_ha_state()
        self.hass.block_till_done()
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        run_coroutine_threadsafe(
            ump.async_turn_off(),
            self.hass.loop).result()
        self.assertEqual(1, len(self.mock_mp_2.service_calls['turn_off']))

        run_coroutine_threadsafe(
            ump.async_turn_on(),
            self.hass.loop).result()
        self.assertEqual(1, len(self.mock_mp_2.service_calls['turn_on']))

        run_coroutine_threadsafe(
            ump.async_mute_volume(True),
            self.hass.loop).result()
        self.assertEqual(1, len(self.mock_mp_2.service_calls['mute_volume']))

        run_coroutine_threadsafe(
            ump.async_set_volume_level(0.5),
            self.hass.loop).result()
        self.assertEqual(
            1, len(self.mock_mp_2.service_calls['set_volume_level']))

        run_coroutine_threadsafe(
            ump.async_media_play(),
            self.hass.loop).result()
        self.assertEqual(1, len(self.mock_mp_2.service_calls['media_play']))

        run_coroutine_threadsafe(
            ump.async_media_pause(),
            self.hass.loop).result()
        self.assertEqual(1, len(self.mock_mp_2.service_calls['media_pause']))

        run_coroutine_threadsafe(
            ump.async_media_previous_track(),
            self.hass.loop).result()
        self.assertEqual(
            1, len(self.mock_mp_2.service_calls['media_previous_track']))

        run_coroutine_threadsafe(
            ump.async_media_next_track(),
            self.hass.loop).result()
        self.assertEqual(
            1, len(self.mock_mp_2.service_calls['media_next_track']))

        run_coroutine_threadsafe(
            ump.async_media_seek(100),
            self.hass.loop).result()
        self.assertEqual(1, len(self.mock_mp_2.service_calls['media_seek']))

        run_coroutine_threadsafe(
            ump.async_play_media('movie', 'batman'),
            self.hass.loop).result()
        self.assertEqual(1, len(self.mock_mp_2.service_calls['play_media']))

        run_coroutine_threadsafe(
            ump.async_volume_up(),
            self.hass.loop).result()
        self.assertEqual(1, len(self.mock_mp_2.service_calls['volume_up']))

        run_coroutine_threadsafe(
            ump.async_volume_down(),
            self.hass.loop).result()
        self.assertEqual(1, len(self.mock_mp_2.service_calls['volume_down']))

        run_coroutine_threadsafe(
            ump.async_media_play_pause(),
            self.hass.loop).result()
        self.assertEqual(
            1, len(self.mock_mp_2.service_calls['media_play_pause']))

        run_coroutine_threadsafe(
            ump.async_select_source('dvd'),
            self.hass.loop).result()
        self.assertEqual(
            1, len(self.mock_mp_2.service_calls['select_source']))

        run_coroutine_threadsafe(
            ump.async_clear_playlist(),
            self.hass.loop).result()
        self.assertEqual(
            1, len(self.mock_mp_2.service_calls['clear_playlist']))

        run_coroutine_threadsafe(
            ump.async_set_shuffle(True),
            self.hass.loop).result()
        self.assertEqual(1, len(self.mock_mp_2.service_calls['shuffle_set']))

    def test_service_call_to_command(self):
        """Test service call to command."""
        config = self.config_children_only
        config['commands'] = {'turn_off': {
            'service': 'test.turn_off', 'data': {}}}
        universal.validate_config(config)

        service = mock_service(self.hass, 'test', 'turn_off')

        ump = universal.UniversalMediaPlayer(self.hass, **config)
        ump.entity_id = media_player.ENTITY_ID_FORMAT.format(config['name'])
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        self.mock_mp_2._state = STATE_PLAYING
        self.mock_mp_2.schedule_update_ha_state()
        self.hass.block_till_done()
        run_coroutine_threadsafe(ump.async_update(), self.hass.loop).result()

        run_coroutine_threadsafe(ump.async_turn_off(), self.hass.loop).result()
        self.assertEqual(1, len(service))

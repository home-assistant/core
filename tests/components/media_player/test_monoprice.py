"""The tests for Monoprice Media player platform."""
import unittest
import voluptuous as vol

from collections import defaultdict

from homeassistant.components.media_player import (
    SUPPORT_TURN_ON, SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP, SUPPORT_SELECT_SOURCE)
from homeassistant.const import STATE_ON, STATE_OFF

from homeassistant.components.media_player.monoprice import (
    MonopriceZone, PLATFORM_SCHEMA)


class MockState(object):
    """Mock for zone state object."""

    def __init__(self):
        """Init zone state."""
        self.power = True
        self.volume = 0
        self.mute = True
        self.source = 1


class MockMonoprice(object):
    """Mock for pymonoprice object."""

    def __init__(self):
        """Init mock object."""
        self.zones = defaultdict(lambda *a: MockState())

    def zone_status(self, zone_id):
        """Get zone status."""
        return self.zones[zone_id]

    def set_source(self, zone_id, source_idx):
        """Set source for zone."""
        self.zones[zone_id].source = source_idx

    def set_power(self, zone_id, power):
        """Turn zone on/off."""
        self.zones[zone_id].power = power

    def set_mute(self, zone_id, mute):
        """Mute/unmute zone."""
        self.zones[zone_id].mute = mute

    def set_volume(self, zone_id, volume):
        """Set volume for zone."""
        self.zones[zone_id].volume = volume


class TestMonopriceSchema(unittest.TestCase):
    """Test Monoprice schema."""

    def test_valid_schema(self):
        """Test valid schema."""
        valid_schema = {
            'platform': 'monoprice',
            'port': '/dev/ttyUSB0',
            'zones': {11: {'name': 'a'},
                      12: {'name': 'a'},
                      13: {'name': 'a'},
                      14: {'name': 'a'},
                      15: {'name': 'a'},
                      16: {'name': 'a'},
                      21: {'name': 'a'},
                      22: {'name': 'a'},
                      23: {'name': 'a'},
                      24: {'name': 'a'},
                      25: {'name': 'a'},
                      26: {'name': 'a'},
                      31: {'name': 'a'},
                      32: {'name': 'a'},
                      33: {'name': 'a'},
                      34: {'name': 'a'},
                      35: {'name': 'a'},
                      36: {'name': 'a'},
                      },
            'sources': {
                1: {'name': 'a'},
                2: {'name': 'a'},
                3: {'name': 'a'},
                4: {'name': 'a'},
                5: {'name': 'a'},
                6: {'name': 'a'}
            }
        }
        PLATFORM_SCHEMA(valid_schema)

    def test_invalid_schemas(self):
        """Test invalid schemas."""
        schemas = (
            {},  # Empty
            None,  # None
            # Missing port
            {
                'platform': 'monoprice',
                'name': 'Name',
                'zones': {11: {'name': 'a'}},
                'sources': {1: {'name': 'b'}},
            },
            # Invalid zone number
            {
                'platform': 'monoprice',
                'port': 'aaa',
                'name': 'Name',
                'zones': {10: {'name': 'a'}},
                'sources': {1: {'name': 'b'}},
            },
            # Invalid source number
            {
                'platform': 'monoprice',
                'port': 'aaa',
                'name': 'Name',
                'zones': {11: {'name': 'a'}},
                'sources': {0: {'name': 'b'}},
            },
            # Zone missing name
            {
                'platform': 'monoprice',
                'port': 'aaa',
                'name': 'Name',
                'zones': {11: {}},
                'sources': {1: {'name': 'b'}},
            },
            # Source missing name
            {
                'platform': 'monoprice',
                'port': 'aaa',
                'name': 'Name',
                'zones': {11: {'name': 'a'}},
                'sources': {1: {}},
            },

        )
        for value in schemas:
            with self.assertRaises(vol.MultipleInvalid):
                PLATFORM_SCHEMA(value)


class TestMonopriceMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    def setUp(self):
        """Set up the test case."""
        self.monoprice = MockMonoprice()
        # Note, source dictionary is unsorted!
        self.media_player = MonopriceZone(self.monoprice, {1: 'one',
                                                           3: 'three',
                                                           2: 'two'},
                                          12, 'Zone name')

    def test_update(self):
        """Test updating values from monoprice."""
        self.assertIsNone(self.media_player.state)
        self.assertIsNone(self.media_player.volume_level)
        self.assertIsNone(self.media_player.is_volume_muted)
        self.assertIsNone(self.media_player.source)

        self.media_player.update()

        self.assertEqual(STATE_ON, self.media_player.state)
        self.assertEqual(0.0, self.media_player.volume_level, 0.0001)
        self.assertTrue(self.media_player.is_volume_muted)
        self.assertEqual('one', self.media_player.source)

    def test_name(self):
        """Test name property."""
        self.assertEqual('Zone name', self.media_player.name)

    def test_state(self):
        """Test state property."""
        self.assertIsNone(self.media_player.state)

        self.media_player.update()
        self.assertEqual(STATE_ON, self.media_player.state)

        self.monoprice.zones[12].power = False
        self.media_player.update()
        self.assertEqual(STATE_OFF, self.media_player.state)

    def test_volume_level(self):
        """Test volume level property."""
        self.assertIsNone(self.media_player.volume_level)
        self.media_player.update()
        self.assertEqual(0.0, self.media_player.volume_level, 0.0001)

        self.monoprice.zones[12].volume = 38
        self.media_player.update()
        self.assertEqual(1.0, self.media_player.volume_level, 0.0001)

        self.monoprice.zones[12].volume = 19
        self.media_player.update()
        self.assertEqual(.5, self.media_player.volume_level, 0.0001)

    def test_is_volume_muted(self):
        """Test volume muted property."""
        self.assertIsNone(self.media_player.is_volume_muted)

        self.media_player.update()
        self.assertTrue(self.media_player.is_volume_muted)

        self.monoprice.zones[12].mute = False
        self.media_player.update()
        self.assertFalse(self.media_player.is_volume_muted)

    def test_supported_features(self):
        """Test supported features property."""
        self.assertEqual(SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET |
                         SUPPORT_VOLUME_STEP | SUPPORT_TURN_ON |
                         SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE,
                         self.media_player.supported_features)

    def test_source(self):
        """Test source property."""
        self.assertIsNone(self.media_player.source)
        self.media_player.update()
        self.assertEqual('one', self.media_player.source)

    def test_media_title(self):
        """Test media title property."""
        self.assertIsNone(self.media_player.media_title)
        self.media_player.update()
        self.assertEqual('one', self.media_player.media_title)

    def test_source_list(self):
        """Test source list property."""
        # Note, the list is sorted!
        self.assertEqual(['one', 'two', 'three'],
                         self.media_player.source_list)

    def test_select_source(self):
        """Test source selection methods."""
        self.media_player.update()

        self.assertEqual('one', self.media_player.source)

        self.media_player.select_source('two')
        self.assertEqual(2, self.monoprice.zones[12].source)
        self.media_player.update()
        self.assertEqual('two', self.media_player.source)

        # Trying to set unknown source
        self.media_player.select_source('no name')
        self.assertEqual(2, self.monoprice.zones[12].source)
        self.media_player.update()
        self.assertEqual('two', self.media_player.source)

    def test_turn_on(self):
        """Test turning on the zone."""
        self.monoprice.zones[12].power = False
        self.media_player.update()
        self.assertEqual(STATE_OFF, self.media_player.state)

        self.media_player.turn_on()
        self.assertTrue(self.monoprice.zones[12].power)
        self.media_player.update()
        self.assertEqual(STATE_ON, self.media_player.state)

    def test_turn_off(self):
        """Test turning off the zone."""
        self.monoprice.zones[12].power = True
        self.media_player.update()
        self.assertEqual(STATE_ON, self.media_player.state)

        self.media_player.turn_off()
        self.assertFalse(self.monoprice.zones[12].power)
        self.media_player.update()
        self.assertEqual(STATE_OFF, self.media_player.state)

    def test_mute_volume(self):
        """Test mute functionality."""
        self.monoprice.zones[12].mute = True
        self.media_player.update()
        self.assertTrue(self.media_player.is_volume_muted)

        self.media_player.mute_volume(False)
        self.assertFalse(self.monoprice.zones[12].mute)
        self.media_player.update()
        self.assertFalse(self.media_player.is_volume_muted)

        self.media_player.mute_volume(True)
        self.assertTrue(self.monoprice.zones[12].mute)
        self.media_player.update()
        self.assertTrue(self.media_player.is_volume_muted)

    def test_set_volume_level(self):
        """Test set volume level."""
        self.media_player.set_volume_level(1.0)
        self.assertEqual(38, self.monoprice.zones[12].volume)
        self.assertTrue(isinstance(self.monoprice.zones[12].volume, int))

        self.media_player.set_volume_level(0.0)
        self.assertEqual(0, self.monoprice.zones[12].volume)
        self.assertTrue(isinstance(self.monoprice.zones[12].volume, int))

        self.media_player.set_volume_level(0.5)
        self.assertEqual(19, self.monoprice.zones[12].volume)
        self.assertTrue(isinstance(self.monoprice.zones[12].volume, int))

    def test_volume_up(self):
        """Test increasing volume by one."""
        self.monoprice.zones[12].volume = 37
        self.media_player.update()
        self.media_player.volume_up()
        self.assertEqual(38, self.monoprice.zones[12].volume)
        self.assertTrue(isinstance(self.monoprice.zones[12].volume, int))

        # Try to raise value beyond max
        self.media_player.update()
        self.media_player.volume_up()
        self.assertEqual(38, self.monoprice.zones[12].volume)
        self.assertTrue(isinstance(self.monoprice.zones[12].volume, int))

    def test_volume_down(self):
        """Test decreasing volume by one."""
        self.monoprice.zones[12].volume = 1
        self.media_player.update()
        self.media_player.volume_down()
        self.assertEqual(0, self.monoprice.zones[12].volume)
        self.assertTrue(isinstance(self.monoprice.zones[12].volume, int))

        # Try to lower value beyond minimum
        self.media_player.update()
        self.media_player.volume_down()
        self.assertEqual(0, self.monoprice.zones[12].volume)
        self.assertTrue(isinstance(self.monoprice.zones[12].volume, int))

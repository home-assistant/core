"""The tests for the Monoprice Blackbird media player platform."""
import unittest
from unittest import mock
import voluptuous as vol

from collections import defaultdict
from homeassistant.components.media_player import (
    DOMAIN, SUPPORT_TURN_ON, SUPPORT_TURN_OFF, SUPPORT_SELECT_SOURCE)
from homeassistant.const import STATE_ON, STATE_OFF

import tests.common
from homeassistant.components.media_player.blackbird import (
    DATA_BLACKBIRD, PLATFORM_SCHEMA, SERVICE_SETALLZONES, setup_platform)


class AttrDict(dict):
    """Helper clas for mocking attributes."""

    def __setattr__(self, name, value):
        """Set attribute."""
        self[name] = value

    def __getattr__(self, item):
        """Get attribute."""
        return self[item]


class MockBlackbird(object):
    """Mock for pyblackbird object."""

    def __init__(self):
        self.zones = defaultdict(lambda: AttrDict(power=True,
                                                  av=1))

    def zone_status(self, zone_id):
        """Get zone status."""
        status = self.zones[zone_id]
        status.zone = zone_id
        return AttrDict(status)

    def set_zone_source(self, zone_id, source_idx):
        """Set source for zone."""
        self.zones[zone_id].source = source_idx

    def set_zone_power(self, zone_id, power):
        """Turn zone on/off."""
        self.zones[zone_id].power = power

    def set_all_zone_source(self, source_idx):
        """Set source for all zones."""
        self.zones[zone_id].source = source_idx


class TestBlackbirdSchema(unittest.TestCase):
    """Test Blackbird schema."""

    def test_valid_schema(self):
        """Test valid schema."""
        valid_schema = {
            'platform': 'blackbird',
            'port': '/dev/ttyUSB0',
            'zones': {1: {'name': 'a'},
                      2: {'name': 'a'},
                      3: {'name': 'a'},
                      4: {'name': 'a'},
                      5: {'name': 'a'},
                      6: {'name': 'a'},
                      7: {'name': 'a'},
                      8: {'name': 'a'},
            },
            'sources': {
                1: {'name': 'a'},
                2: {'name': 'a'},
                3: {'name': 'a'},
                4: {'name': 'a'},
                5: {'name': 'a'},
                6: {'name': 'a'},
                7: {'name': 'a'},
                8: {'name': 'a'},
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
                'platform': 'blackbird',
                'name': 'Name',
                'zones': {1: {'name': 'a'}},
                'sources': {1: {'name': 'b'}},
            },
            # Invalid zone number
            {
                'platform': 'blackbird',
                'port': 'aaa',
                'name': 'Name',
                'zones': {11: {'name': 'a'}},
                'sources': {1: {'name': 'b'}},
            },
             # Invalid source number
            {
                'platform': 'blackbird',
                'port': 'aaa',
                'name': 'Name',
                'zones': {1: {'name': 'a'}},
                'sources': {9: {'name': 'b'}},
            },
             # Zone missing name
            {
                'platform': 'blackbird',
                'port': 'aaa',
                'name': 'Name',
                'zones': {1: {}},
                'sources': {1: {'name': 'b'}},
            },
             # Source missing name
            {
                'platform': 'blackbird',
                'port': 'aaa',
                'name': 'Name',
                'zones': {1: {'name': 'a'}},
                'sources': {1: {}},
            },


        )
        for value in schemas:
            with self.assertRaises(vol.MultipleInvalid):
                PLATFORM_SCHEMA(value)


class TestBlackbirdMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    def setUp(self):
        """Set up the test case."""
        self.blackbird = MockBlackbird()
        self.hass = tests.common.get_test_home_assistant()
        self.hass.start()
        # Note, source dictionary is unsorted!
        with mock.patch('pyblackbird.get_blackbird',
                        new=lambda *a: self.blackbird):
            setup_platform(self.hass, {
                'platform': 'blackbird',
                'port': '/dev/ttyUSB0',
                'name': 'Name',
                'zones': {3: {'name': 'Zone name'}},
                'sources': {1: {'name': 'one'},
                            3: {'name': 'three'},
                            2: {'name': 'two'}},
            }, lambda *args, **kwargs: None, {})
            self.hass.block_till_done()
        self.media_player = self.hass.data[DATA_BLACKBIRD][0]
        self.media_player.hass = self.hass
        self.media_player.entity_id = 'media_player.zone_1'

    def tearDown(self):
        """Tear down the test case."""
        self.hass.stop()

    def test_setup_platform(self, *args):
        """Test setting up platform."""
        # One service must be registered
        self.assertTrue(self.hass.services.has_service(DOMAIN,
                                                       SERVICE_SETALLZONES))
        self.assertEqual(len(self.hass.data[DATA_BLACKBIRD]), 1)
        self.assertEqual(self.hass.data[DATA_BLACKBIRD][0].name, 'Zone name')

    def test_service_calls_with_entity_id(self):
        """Test set all zone source service call."""
        self.media_player.update()
        self.assertEqual('Zone name', self.media_player.name)
        self.assertEqual(STATE_ON, self.media_player.state)
        self.assertEqual('one', self.media_player.source)
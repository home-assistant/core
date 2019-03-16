"""The tests for Monoprice Media player platform."""
import unittest
from unittest import mock
import voluptuous as vol

from collections import defaultdict
from homeassistant.components.media_player.const import (
    DOMAIN, SUPPORT_TURN_ON, SUPPORT_TURN_OFF, SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET, SUPPORT_VOLUME_STEP, SUPPORT_SELECT_SOURCE)
from homeassistant.const import STATE_ON, STATE_OFF

import tests.common
from homeassistant.components.monoprice.media_player import (
    DATA_MONOPRICE, PLATFORM_SCHEMA, SERVICE_SNAPSHOT,
    SERVICE_RESTORE, setup_platform)
import pytest


class AttrDict(dict):
    """Helper class for mocking attributes."""

    def __setattr__(self, name, value):
        """Set attribute."""
        self[name] = value

    def __getattr__(self, item):
        """Get attribute."""
        return self[item]


class MockMonoprice:
    """Mock for pymonoprice object."""

    def __init__(self):
        """Init mock object."""
        self.zones = defaultdict(lambda: AttrDict(power=True,
                                                  volume=0,
                                                  mute=True,
                                                  source=1))

    def zone_status(self, zone_id):
        """Get zone status."""
        status = self.zones[zone_id]
        status.zone = zone_id
        return AttrDict(status)

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

    def restore_zone(self, zone):
        """Restore zone status."""
        self.zones[zone.zone] = AttrDict(zone)


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
            with pytest.raises(vol.MultipleInvalid):
                PLATFORM_SCHEMA(value)


class TestMonopriceMediaPlayer(unittest.TestCase):
    """Test the media_player module."""

    def setUp(self):
        """Set up the test case."""
        self.monoprice = MockMonoprice()
        self.hass = tests.common.get_test_home_assistant()
        self.hass.start()
        # Note, source dictionary is unsorted!
        with mock.patch('pymonoprice.get_monoprice',
                        new=lambda *a: self.monoprice):
            setup_platform(self.hass, {
                'platform': 'monoprice',
                'port': '/dev/ttyS0',
                'name': 'Name',
                'zones': {12: {'name': 'Zone name'}},
                'sources': {1: {'name': 'one'},
                            3: {'name': 'three'},
                            2: {'name': 'two'}},
            }, lambda *args, **kwargs: None, {})
            self.hass.block_till_done()
        self.media_player = self.hass.data[DATA_MONOPRICE][0]
        self.media_player.hass = self.hass
        self.media_player.entity_id = 'media_player.zone_1'

    def tearDown(self):
        """Tear down the test case."""
        self.hass.stop()

    def test_setup_platform(self, *args):
        """Test setting up platform."""
        # Two services must be registered
        assert self.hass.services.has_service(DOMAIN, SERVICE_RESTORE)
        assert self.hass.services.has_service(DOMAIN, SERVICE_SNAPSHOT)
        assert len(self.hass.data[DATA_MONOPRICE]) == 1
        assert self.hass.data[DATA_MONOPRICE][0].name == 'Zone name'

    def test_service_calls_with_entity_id(self):
        """Test snapshot save/restore service calls."""
        self.media_player.update()
        assert 'Zone name' == self.media_player.name
        assert STATE_ON == self.media_player.state
        assert 0.0 == self.media_player.volume_level, 0.0001
        assert self.media_player.is_volume_muted
        assert 'one' == self.media_player.source

        # Saving default values
        self.hass.services.call(DOMAIN, SERVICE_SNAPSHOT,
                                {'entity_id': 'media_player.zone_1'},
                                blocking=True)
        # self.hass.block_till_done()

        # Changing media player to new state
        self.media_player.set_volume_level(1)
        self.media_player.select_source('two')
        self.media_player.mute_volume(False)
        self.media_player.turn_off()

        # Checking that values were indeed changed
        self.media_player.update()
        assert 'Zone name' == self.media_player.name
        assert STATE_OFF == self.media_player.state
        assert 1.0 == self.media_player.volume_level, 0.0001
        assert not self.media_player.is_volume_muted
        assert 'two' == self.media_player.source

        # Restoring wrong media player to its previous state
        # Nothing should be done
        self.hass.services.call(DOMAIN, SERVICE_RESTORE,
                                {'entity_id': 'media.not_existing'},
                                blocking=True)
        # self.hass.block_till_done()

        # Checking that values were not (!) restored
        self.media_player.update()
        assert 'Zone name' == self.media_player.name
        assert STATE_OFF == self.media_player.state
        assert 1.0 == self.media_player.volume_level, 0.0001
        assert not self.media_player.is_volume_muted
        assert 'two' == self.media_player.source

        # Restoring media player to its previous state
        self.hass.services.call(DOMAIN, SERVICE_RESTORE,
                                {'entity_id': 'media_player.zone_1'},
                                blocking=True)
        self.hass.block_till_done()

        # Checking that values were restored
        assert 'Zone name' == self.media_player.name
        assert STATE_ON == self.media_player.state
        assert 0.0 == self.media_player.volume_level, 0.0001
        assert self.media_player.is_volume_muted
        assert 'one' == self.media_player.source

    def test_service_calls_without_entity_id(self):
        """Test snapshot save/restore service calls."""
        self.media_player.update()
        assert 'Zone name' == self.media_player.name
        assert STATE_ON == self.media_player.state
        assert 0.0 == self.media_player.volume_level, 0.0001
        assert self.media_player.is_volume_muted
        assert 'one' == self.media_player.source

        # Restoring media player
        # since there is no snapshot, nothing should be done
        self.hass.services.call(DOMAIN, SERVICE_RESTORE, blocking=True)
        self.hass.block_till_done()
        self.media_player.update()
        assert 'Zone name' == self.media_player.name
        assert STATE_ON == self.media_player.state
        assert 0.0 == self.media_player.volume_level, 0.0001
        assert self.media_player.is_volume_muted
        assert 'one' == self.media_player.source

        # Saving default values
        self.hass.services.call(DOMAIN, SERVICE_SNAPSHOT, blocking=True)
        self.hass.block_till_done()

        # Changing media player to new state
        self.media_player.set_volume_level(1)
        self.media_player.select_source('two')
        self.media_player.mute_volume(False)
        self.media_player.turn_off()

        # Checking that values were indeed changed
        self.media_player.update()
        assert 'Zone name' == self.media_player.name
        assert STATE_OFF == self.media_player.state
        assert 1.0 == self.media_player.volume_level, 0.0001
        assert not self.media_player.is_volume_muted
        assert 'two' == self.media_player.source

        # Restoring media player to its previous state
        self.hass.services.call(DOMAIN, SERVICE_RESTORE, blocking=True)
        self.hass.block_till_done()

        # Checking that values were restored
        assert 'Zone name' == self.media_player.name
        assert STATE_ON == self.media_player.state
        assert 0.0 == self.media_player.volume_level, 0.0001
        assert self.media_player.is_volume_muted
        assert 'one' == self.media_player.source

    def test_update(self):
        """Test updating values from monoprice."""
        assert self.media_player.state is None
        assert self.media_player.volume_level is None
        assert self.media_player.is_volume_muted is None
        assert self.media_player.source is None

        self.media_player.update()

        assert STATE_ON == self.media_player.state
        assert 0.0 == self.media_player.volume_level, 0.0001
        assert self.media_player.is_volume_muted
        assert 'one' == self.media_player.source

    def test_name(self):
        """Test name property."""
        assert 'Zone name' == self.media_player.name

    def test_state(self):
        """Test state property."""
        assert self.media_player.state is None

        self.media_player.update()
        assert STATE_ON == self.media_player.state

        self.monoprice.zones[12].power = False
        self.media_player.update()
        assert STATE_OFF == self.media_player.state

    def test_volume_level(self):
        """Test volume level property."""
        assert self.media_player.volume_level is None
        self.media_player.update()
        assert 0.0 == self.media_player.volume_level, 0.0001

        self.monoprice.zones[12].volume = 38
        self.media_player.update()
        assert 1.0 == self.media_player.volume_level, 0.0001

        self.monoprice.zones[12].volume = 19
        self.media_player.update()
        assert .5 == self.media_player.volume_level, 0.0001

    def test_is_volume_muted(self):
        """Test volume muted property."""
        assert self.media_player.is_volume_muted is None

        self.media_player.update()
        assert self.media_player.is_volume_muted

        self.monoprice.zones[12].mute = False
        self.media_player.update()
        assert not self.media_player.is_volume_muted

    def test_supported_features(self):
        """Test supported features property."""
        assert SUPPORT_VOLUME_MUTE | SUPPORT_VOLUME_SET | \
            SUPPORT_VOLUME_STEP | SUPPORT_TURN_ON | \
            SUPPORT_TURN_OFF | SUPPORT_SELECT_SOURCE == \
            self.media_player.supported_features

    def test_source(self):
        """Test source property."""
        assert self.media_player.source is None
        self.media_player.update()
        assert 'one' == self.media_player.source

    def test_media_title(self):
        """Test media title property."""
        assert self.media_player.media_title is None
        self.media_player.update()
        assert 'one' == self.media_player.media_title

    def test_source_list(self):
        """Test source list property."""
        # Note, the list is sorted!
        assert ['one', 'two', 'three'] == \
            self.media_player.source_list

    def test_select_source(self):
        """Test source selection methods."""
        self.media_player.update()

        assert 'one' == self.media_player.source

        self.media_player.select_source('two')
        assert 2 == self.monoprice.zones[12].source
        self.media_player.update()
        assert 'two' == self.media_player.source

        # Trying to set unknown source
        self.media_player.select_source('no name')
        assert 2 == self.monoprice.zones[12].source
        self.media_player.update()
        assert 'two' == self.media_player.source

    def test_turn_on(self):
        """Test turning on the zone."""
        self.monoprice.zones[12].power = False
        self.media_player.update()
        assert STATE_OFF == self.media_player.state

        self.media_player.turn_on()
        assert self.monoprice.zones[12].power
        self.media_player.update()
        assert STATE_ON == self.media_player.state

    def test_turn_off(self):
        """Test turning off the zone."""
        self.monoprice.zones[12].power = True
        self.media_player.update()
        assert STATE_ON == self.media_player.state

        self.media_player.turn_off()
        assert not self.monoprice.zones[12].power
        self.media_player.update()
        assert STATE_OFF == self.media_player.state

    def test_mute_volume(self):
        """Test mute functionality."""
        self.monoprice.zones[12].mute = True
        self.media_player.update()
        assert self.media_player.is_volume_muted

        self.media_player.mute_volume(False)
        assert not self.monoprice.zones[12].mute
        self.media_player.update()
        assert not self.media_player.is_volume_muted

        self.media_player.mute_volume(True)
        assert self.monoprice.zones[12].mute
        self.media_player.update()
        assert self.media_player.is_volume_muted

    def test_set_volume_level(self):
        """Test set volume level."""
        self.media_player.set_volume_level(1.0)
        assert 38 == self.monoprice.zones[12].volume
        assert isinstance(self.monoprice.zones[12].volume, int)

        self.media_player.set_volume_level(0.0)
        assert 0 == self.monoprice.zones[12].volume
        assert isinstance(self.monoprice.zones[12].volume, int)

        self.media_player.set_volume_level(0.5)
        assert 19 == self.monoprice.zones[12].volume
        assert isinstance(self.monoprice.zones[12].volume, int)

    def test_volume_up(self):
        """Test increasing volume by one."""
        self.monoprice.zones[12].volume = 37
        self.media_player.update()
        self.media_player.volume_up()
        assert 38 == self.monoprice.zones[12].volume
        assert isinstance(self.monoprice.zones[12].volume, int)

        # Try to raise value beyond max
        self.media_player.update()
        self.media_player.volume_up()
        assert 38 == self.monoprice.zones[12].volume
        assert isinstance(self.monoprice.zones[12].volume, int)

    def test_volume_down(self):
        """Test decreasing volume by one."""
        self.monoprice.zones[12].volume = 1
        self.media_player.update()
        self.media_player.volume_down()
        assert 0 == self.monoprice.zones[12].volume
        assert isinstance(self.monoprice.zones[12].volume, int)

        # Try to lower value beyond minimum
        self.media_player.update()
        self.media_player.volume_down()
        assert 0 == self.monoprice.zones[12].volume
        assert isinstance(self.monoprice.zones[12].volume, int)

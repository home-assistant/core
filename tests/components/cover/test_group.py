"""The tests for the group cover platform."""

import unittest
from datetime import timedelta
import homeassistant.util.dt as dt_util

from homeassistant import setup
from homeassistant.components import cover
from tests.common import (
    assert_setup_component, get_test_home_assistant, fire_time_changed)

GROUP_COVER = 'cover.cover_group'
DEMO_COVER = 'cover.kitchen_window'
DEMO_COVER_POS = 'cover.hall_window'
DEMO_COVER_TILT = 'cover.living_room_window'
DEMO_TILT = 'cover.tilt_demo'

CONFIG = {
    'cover': [
        {'platform': 'demo'},
        {'platform': 'group',
         'entities': [
             DEMO_COVER, DEMO_COVER_POS, DEMO_COVER_TILT, DEMO_TILT]}
    ]
}


class TestMultiCover(unittest.TestCase):
    """Test the group cover platform."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_attributes(self):
        """Test state attributes after setup."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG)

        state = self.hass.states.get(GROUP_COVER)
        attr = state.attributes

        self.assertEqual(state.state, 'open')
        self.assertEqual(attr.get('current_position'), 100)
        self.assertEqual(attr.get('current_tilt_position'), 50)
        self.assertEqual(attr.get('supported_features'), 255)
        self.assertTrue(attr.get('assumed_state'))

    def test_current_cover_position(self):
        """Test different current cover positions."""
        with assert_setup_component(2, 'cover'):
            setup.setup_component(self.hass, 'cover', CONFIG)

        self.assertEqual(self.hass.states.get(GROUP_COVER)
                         .attributes.get('current_position'), 100)

        self.hass.states.set(
            DEMO_COVER_POS, 'open',
            {'current_position': 70, 'supported_features': 15})
        self.hass.block_till_done()

        self.assertEqual(self.hass.states.get(GROUP_COVER)
                         .attributes.get('current_position'), 70)

        self.hass.states.remove(DEMO_COVER_POS)
        self.hass.states.set(
            DEMO_COVER_TILT, 'open',
            {'current_position': 80, 'supported_features': 15})
        self.hass.block_till_done()

        self.assertEqual(self.hass.states.get(GROUP_COVER)
                         .attributes.get('current_position'), 80)

        self.hass.states.remove(DEMO_COVER_TILT)
        self.hass.states.set(DEMO_COVER, 'closed')
        self.hass.block_till_done()

        self.assertEqual(self.hass.states.get(GROUP_COVER).state, 'closed')

        self.hass.states.remove(DEMO_COVER)
        self.hass.block_till_done()

        self.assertEqual(self.hass.states.get(GROUP_COVER).state, 'open')

    def test_current_tilt_position(self):
        """Test different current cover tilt positions."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG)

        self.hass.states.set(
            DEMO_TILT, 'open',
            {'current_tilt_position': 60, 'supported_features': 255})
        self.hass.block_till_done()

        self.assertEqual(self.hass.states.get(GROUP_COVER)
                         .attributes.get('current_tilt_position'), 100)

        self.hass.states.set(
            DEMO_TILT, 'open',
            {'current_tilt_position': 50, 'supported_features': 255})
        self.hass.block_till_done()

        self.assertEqual(self.hass.states.get(GROUP_COVER)
                         .attributes.get('current_tilt_position'), 50)

    def test_open_covers(self):
        """Test open cover function."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG)

        cover.open_cover(self.hass, GROUP_COVER)
        self.hass.block_till_done()
        for _ in range(10):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(GROUP_COVER)
        self.assertEqual(state.state, 'open')
        self.assertEqual(state.attributes.get('current_position'), 100)

        self.assertEqual(self.hass.states.get(DEMO_COVER).state, 'open')
        self.assertEqual(self.hass.states.get(DEMO_COVER_POS)
                         .attributes.get('current_position'), 100)
        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_position'), 100)

    def test_close_covers(self):
        """Test close cover function."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG)

        cover.close_cover(self.hass, GROUP_COVER)
        self.hass.block_till_done()
        for _ in range(10):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(GROUP_COVER)
        self.assertEqual(state.state, 'closed')
        self.assertEqual(state.attributes.get('current_position'), 0)

        self.assertEqual(self.hass.states.get(DEMO_COVER).state, 'closed')
        self.assertEqual(self.hass.states.get(DEMO_COVER_POS)
                         .attributes.get('current_position'), 0)
        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_position'), 0)

    def test_stop_covers(self):
        """Test stop cover function."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG)

        cover.open_cover(self.hass, GROUP_COVER)
        self.hass.block_till_done()
        future = dt_util.utcnow() + timedelta(seconds=1)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()
        cover.stop_cover(self.hass, GROUP_COVER)
        self.hass.block_till_done()
        future = dt_util.utcnow() + timedelta(seconds=1)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()

        state = self.hass.states.get(GROUP_COVER)
        self.assertEqual(state.state, 'open')
        self.assertEqual(state.attributes.get('current_position'), 100)

        self.assertEqual(self.hass.states.get(DEMO_COVER).state, 'open')
        self.assertEqual(self.hass.states.get(DEMO_COVER_POS)
                         .attributes.get('current_position'), 20)
        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_position'), 80)

    def test_set_cover_position(self):
        """Test set cover position function."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG)

        cover.set_cover_position(self.hass, 50, GROUP_COVER)
        self.hass.block_till_done()
        for _ in range(4):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(GROUP_COVER)
        self.assertEqual(state.state, 'open')
        self.assertEqual(state.attributes.get('current_position'), 50)

        self.assertEqual(self.hass.states.get(DEMO_COVER).state, 'closed')
        self.assertEqual(self.hass.states.get(DEMO_COVER_POS)
                         .attributes.get('current_position'), 50)
        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_position'), 50)

    def test_open_tilts(self):
        """Test open tilt function."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG)

        cover.open_cover_tilt(self.hass, GROUP_COVER)
        self.hass.block_till_done()
        for _ in range(5):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(GROUP_COVER)
        self.assertEqual(state.state, 'open')
        self.assertEqual(state.attributes.get('current_tilt_position'), 100)

        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_tilt_position'), 100)

    def test_close_tilts(self):
        """Test close tilt function."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG)

        cover.close_cover_tilt(self.hass, GROUP_COVER)
        self.hass.block_till_done()
        for _ in range(5):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(GROUP_COVER)
        self.assertEqual(state.state, 'open')
        self.assertEqual(state.attributes.get('current_tilt_position'), 0)

        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_tilt_position'), 0)

    def test_stop_tilts(self):
        """Test stop tilts function."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG)

        cover.open_cover_tilt(self.hass, GROUP_COVER)
        self.hass.block_till_done()
        future = dt_util.utcnow() + timedelta(seconds=1)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()
        cover.stop_cover_tilt(self.hass, GROUP_COVER)
        self.hass.block_till_done()
        future = dt_util.utcnow() + timedelta(seconds=1)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()

        state = self.hass.states.get(GROUP_COVER)
        self.assertEqual(state.state, 'open')
        self.assertEqual(state.attributes.get('current_tilt_position'), 60)

        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_tilt_position'), 60)

    def test_set_tilt_positions(self):
        """Test set tilt position function."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG)

        cover.set_cover_tilt_position(self.hass, 80, GROUP_COVER)
        self.hass.block_till_done()
        for _ in range(3):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(GROUP_COVER)
        self.assertEqual(state.state, 'open')
        self.assertEqual(state.attributes.get('current_tilt_position'), 80)

        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_tilt_position'), 80)

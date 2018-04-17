"""The tests for the group cover platform."""

import unittest
from datetime import timedelta
import homeassistant.util.dt as dt_util

from homeassistant import setup
from homeassistant.components import cover
from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION, ATTR_CURRENT_TILT_POSITION, DOMAIN)
from homeassistant.components.cover.group import DEFAULT_NAME
from homeassistant.const import (
    ATTR_ASSUMED_STATE, ATTR_FRIENDLY_NAME, ATTR_SUPPORTED_FEATURES,
    CONF_ENTITIES, STATE_OPEN, STATE_CLOSED)
from tests.common import (
    assert_setup_component, get_test_home_assistant, fire_time_changed)

COVER_GROUP = 'cover.cover_group'
DEMO_COVER = 'cover.kitchen_window'
DEMO_COVER_POS = 'cover.hall_window'
DEMO_COVER_TILT = 'cover.living_room_window'
DEMO_TILT = 'cover.tilt_demo'

CONFIG = {
    DOMAIN: [
        {'platform': 'demo'},
        {'platform': 'group',
         CONF_ENTITIES: [
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
        """Test handling of state attributes."""
        config = {DOMAIN: {'platform': 'group', CONF_ENTITIES: [
            DEMO_COVER, DEMO_COVER_POS, DEMO_COVER_TILT, DEMO_TILT]}}

        with assert_setup_component(1, DOMAIN):
            assert setup.setup_component(self.hass, DOMAIN, config)

        state = self.hass.states.get(COVER_GROUP)
        attr = state.attributes
        self.assertEqual(state.state, STATE_CLOSED)
        self.assertEqual(attr.get(ATTR_FRIENDLY_NAME), DEFAULT_NAME)
        self.assertEqual(attr.get(ATTR_ASSUMED_STATE), None)
        self.assertEqual(attr.get(ATTR_SUPPORTED_FEATURES), 0)
        self.assertEqual(attr.get(ATTR_CURRENT_POSITION), None)
        self.assertEqual(attr.get(ATTR_CURRENT_TILT_POSITION), None)

        # Add Entity that supports open / close / stop
        self.hass.states.set(
            DEMO_COVER, STATE_OPEN, {ATTR_SUPPORTED_FEATURES: 11})
        self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        attr = state.attributes
        self.assertEqual(state.state, STATE_OPEN)
        self.assertEqual(attr.get(ATTR_ASSUMED_STATE), None)
        self.assertEqual(attr.get(ATTR_SUPPORTED_FEATURES), 11)
        self.assertEqual(attr.get(ATTR_CURRENT_POSITION), None)
        self.assertEqual(attr.get(ATTR_CURRENT_TILT_POSITION), None)

        # Add Entity that supports set_cover_position
        self.hass.states.set(
            DEMO_COVER_POS, STATE_OPEN,
            {ATTR_SUPPORTED_FEATURES: 4, ATTR_CURRENT_POSITION: 70})
        self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        attr = state.attributes
        self.assertEqual(state.state, STATE_OPEN)
        self.assertEqual(attr.get(ATTR_ASSUMED_STATE), None)
        self.assertEqual(attr.get(ATTR_SUPPORTED_FEATURES), 15)
        self.assertEqual(attr.get(ATTR_CURRENT_POSITION), 70)
        self.assertEqual(attr.get(ATTR_CURRENT_TILT_POSITION), None)

        # Add Entity that supports open tilt / close tilt / stop tilt
        self.hass.states.set(
            DEMO_TILT, STATE_OPEN, {ATTR_SUPPORTED_FEATURES: 112})
        self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        attr = state.attributes
        self.assertEqual(state.state, STATE_OPEN)
        self.assertEqual(attr.get(ATTR_ASSUMED_STATE), None)
        self.assertEqual(attr.get(ATTR_SUPPORTED_FEATURES), 127)
        self.assertEqual(attr.get(ATTR_CURRENT_POSITION), 70)
        self.assertEqual(attr.get(ATTR_CURRENT_TILT_POSITION), None)

        # Add Entity that supports set_tilt_position
        self.hass.states.set(
            DEMO_COVER_TILT, STATE_OPEN,
            {ATTR_SUPPORTED_FEATURES: 128, ATTR_CURRENT_TILT_POSITION: 60})
        self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        attr = state.attributes
        self.assertEqual(state.state, STATE_OPEN)
        self.assertEqual(attr.get(ATTR_ASSUMED_STATE), None)
        self.assertEqual(attr.get(ATTR_SUPPORTED_FEATURES), 255)
        self.assertEqual(attr.get(ATTR_CURRENT_POSITION), 70)
        self.assertEqual(attr.get(ATTR_CURRENT_TILT_POSITION), 60)

        # ### Test assumed state ###
        # ##########################

        # For covers
        self.hass.states.set(
            DEMO_COVER, STATE_OPEN,
            {ATTR_SUPPORTED_FEATURES: 4, ATTR_CURRENT_POSITION: 100})
        self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        attr = state.attributes
        self.assertEqual(state.state, STATE_OPEN)
        self.assertEqual(attr.get(ATTR_ASSUMED_STATE), True)
        self.assertEqual(attr.get(ATTR_SUPPORTED_FEATURES), 244)
        self.assertEqual(attr.get(ATTR_CURRENT_POSITION), 100)
        self.assertEqual(attr.get(ATTR_CURRENT_TILT_POSITION), 60)

        self.hass.states.remove(DEMO_COVER)
        self.hass.block_till_done()
        self.hass.states.remove(DEMO_COVER_POS)
        self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        attr = state.attributes
        self.assertEqual(state.state, STATE_OPEN)
        self.assertEqual(attr.get(ATTR_ASSUMED_STATE), None)
        self.assertEqual(attr.get(ATTR_SUPPORTED_FEATURES), 240)
        self.assertEqual(attr.get(ATTR_CURRENT_POSITION), None)
        self.assertEqual(attr.get(ATTR_CURRENT_TILT_POSITION), 60)

        # For tilts
        self.hass.states.set(
            DEMO_TILT, STATE_OPEN,
            {ATTR_SUPPORTED_FEATURES: 128, ATTR_CURRENT_TILT_POSITION: 100})
        self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        attr = state.attributes
        self.assertEqual(state.state, STATE_OPEN)
        self.assertEqual(attr.get(ATTR_ASSUMED_STATE), True)
        self.assertEqual(attr.get(ATTR_SUPPORTED_FEATURES), 128)
        self.assertEqual(attr.get(ATTR_CURRENT_POSITION), None)
        self.assertEqual(attr.get(ATTR_CURRENT_TILT_POSITION), 100)

        self.hass.states.remove(DEMO_COVER_TILT)
        self.hass.states.set(DEMO_TILT, STATE_CLOSED)
        self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        attr = state.attributes
        self.assertEqual(state.state, STATE_CLOSED)
        self.assertEqual(attr.get(ATTR_ASSUMED_STATE), None)
        self.assertEqual(attr.get(ATTR_SUPPORTED_FEATURES), 0)
        self.assertEqual(attr.get(ATTR_CURRENT_POSITION), None)
        self.assertEqual(attr.get(ATTR_CURRENT_TILT_POSITION), None)

        self.hass.states.set(
            DEMO_TILT, STATE_CLOSED, {ATTR_ASSUMED_STATE: True})
        self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        attr = state.attributes
        self.assertEqual(attr.get(ATTR_ASSUMED_STATE), True)

    def test_open_covers(self):
        """Test open cover function."""
        with assert_setup_component(2, DOMAIN):
            assert setup.setup_component(self.hass, DOMAIN, CONFIG)

        cover.open_cover(self.hass, COVER_GROUP)
        self.hass.block_till_done()
        for _ in range(10):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        self.assertEqual(state.state, STATE_OPEN)
        self.assertEqual(state.attributes.get(ATTR_CURRENT_POSITION), 100)

        self.assertEqual(self.hass.states.get(DEMO_COVER).state, STATE_OPEN)
        self.assertEqual(self.hass.states.get(DEMO_COVER_POS)
                         .attributes.get(ATTR_CURRENT_POSITION), 100)
        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get(ATTR_CURRENT_POSITION), 100)

    def test_close_covers(self):
        """Test close cover function."""
        with assert_setup_component(2, DOMAIN):
            assert setup.setup_component(self.hass, DOMAIN, CONFIG)

        cover.close_cover(self.hass, COVER_GROUP)
        self.hass.block_till_done()
        for _ in range(10):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        self.assertEqual(state.state, STATE_CLOSED)
        self.assertEqual(state.attributes.get(ATTR_CURRENT_POSITION), 0)

        self.assertEqual(self.hass.states.get(DEMO_COVER).state, STATE_CLOSED)
        self.assertEqual(self.hass.states.get(DEMO_COVER_POS)
                         .attributes.get(ATTR_CURRENT_POSITION), 0)
        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get(ATTR_CURRENT_POSITION), 0)

    def test_stop_covers(self):
        """Test stop cover function."""
        with assert_setup_component(2, DOMAIN):
            assert setup.setup_component(self.hass, DOMAIN, CONFIG)

        cover.open_cover(self.hass, COVER_GROUP)
        self.hass.block_till_done()
        future = dt_util.utcnow() + timedelta(seconds=1)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()
        cover.stop_cover(self.hass, COVER_GROUP)
        self.hass.block_till_done()
        future = dt_util.utcnow() + timedelta(seconds=1)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        self.assertEqual(state.state, STATE_OPEN)
        self.assertEqual(state.attributes.get(ATTR_CURRENT_POSITION), 100)

        self.assertEqual(self.hass.states.get(DEMO_COVER).state, STATE_OPEN)
        self.assertEqual(self.hass.states.get(DEMO_COVER_POS)
                         .attributes.get(ATTR_CURRENT_POSITION), 20)
        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get(ATTR_CURRENT_POSITION), 80)

    def test_set_cover_position(self):
        """Test set cover position function."""
        with assert_setup_component(2, DOMAIN):
            assert setup.setup_component(self.hass, DOMAIN, CONFIG)

        cover.set_cover_position(self.hass, 50, COVER_GROUP)
        self.hass.block_till_done()
        for _ in range(4):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        self.assertEqual(state.state, STATE_OPEN)
        self.assertEqual(state.attributes.get(ATTR_CURRENT_POSITION), 50)

        self.assertEqual(self.hass.states.get(DEMO_COVER).state, STATE_CLOSED)
        self.assertEqual(self.hass.states.get(DEMO_COVER_POS)
                         .attributes.get(ATTR_CURRENT_POSITION), 50)
        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get(ATTR_CURRENT_POSITION), 50)

    def test_open_tilts(self):
        """Test open tilt function."""
        with assert_setup_component(2, DOMAIN):
            assert setup.setup_component(self.hass, DOMAIN, CONFIG)

        cover.open_cover_tilt(self.hass, COVER_GROUP)
        self.hass.block_till_done()
        for _ in range(5):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        self.assertEqual(state.state, STATE_OPEN)
        self.assertEqual(state.attributes.get(ATTR_CURRENT_TILT_POSITION), 100)

        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get(ATTR_CURRENT_TILT_POSITION), 100)

    def test_close_tilts(self):
        """Test close tilt function."""
        with assert_setup_component(2, DOMAIN):
            assert setup.setup_component(self.hass, DOMAIN, CONFIG)

        cover.close_cover_tilt(self.hass, COVER_GROUP)
        self.hass.block_till_done()
        for _ in range(5):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        self.assertEqual(state.state, STATE_OPEN)
        self.assertEqual(state.attributes.get(ATTR_CURRENT_TILT_POSITION), 0)

        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get(ATTR_CURRENT_TILT_POSITION), 0)

    def test_stop_tilts(self):
        """Test stop tilts function."""
        with assert_setup_component(2, DOMAIN):
            assert setup.setup_component(self.hass, DOMAIN, CONFIG)

        cover.open_cover_tilt(self.hass, COVER_GROUP)
        self.hass.block_till_done()
        future = dt_util.utcnow() + timedelta(seconds=1)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()
        cover.stop_cover_tilt(self.hass, COVER_GROUP)
        self.hass.block_till_done()
        future = dt_util.utcnow() + timedelta(seconds=1)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        self.assertEqual(state.state, STATE_OPEN)
        self.assertEqual(state.attributes.get(ATTR_CURRENT_TILT_POSITION), 60)

        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get(ATTR_CURRENT_TILT_POSITION), 60)

    def test_set_tilt_positions(self):
        """Test set tilt position function."""
        with assert_setup_component(2, DOMAIN):
            assert setup.setup_component(self.hass, DOMAIN, CONFIG)

        cover.set_cover_tilt_position(self.hass, 80, COVER_GROUP)
        self.hass.block_till_done()
        for _ in range(3):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(COVER_GROUP)
        self.assertEqual(state.state, STATE_OPEN)
        self.assertEqual(state.attributes.get(ATTR_CURRENT_TILT_POSITION), 80)

        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get(ATTR_CURRENT_TILT_POSITION), 80)

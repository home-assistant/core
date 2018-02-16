"""The tests for the cover multicover platform."""

import unittest
from datetime import timedelta
import homeassistant.util.dt as dt_util

from homeassistant import setup
from homeassistant.core import State
from homeassistant.components import cover
from homeassistant.components.zwave.const import EVENT_NETWORK_READY
from tests.common import (
    assert_setup_component, get_test_home_assistant,
    fire_time_changed, mock_state_change_event)

MULTICOVER = 'cover.test_multicover'
DEMO_COVER = 'cover.kitchen_window'
DEMO_COVER_POS = 'cover.hall_window'
DEMO_COVER_TILT = 'cover.living_room_window'

CONFIG = {
    'cover': [
        {'platform': 'demo'},
        {'platform': 'multicover',
         'covers': {
             'test_multicover': {
                 'friendly_name': "Test Multicover",
                 'entity_id': [
                     DEMO_COVER, DEMO_COVER_POS, DEMO_COVER_TILT,
                     'cover.test', 'cover.test_multicover', 'demo.demo'
                 ],
             }
         }}
    ]
}

CONFIG_TILT = {
    'cover': [
        {'platform': 'demo'},
        {'platform': 'multicover',
         'covers': {
             'test_multicover': {
                 'friendly_name': "Test Multicover",
                 'tilt': True,
                 'entity_id': [
                     DEMO_COVER, DEMO_COVER_POS,
                     DEMO_COVER_TILT, 'cover.tilt_demo'
                 ],
             }
         }}
    ]
}

CONFIG_WINTERPROTECTION = {
    'cover': [
        {'platform': 'demo'},
        {'platform': 'multicover',
         'covers': {
             'test_multicover': {
                 'friendly_name': "Test Multicover",
                 'winter_protection': {
                     'close_position': 10,
                     'open_position': 90,
                     'temperature': 5,
                     'temperature_sensor': 'sensor.temperature',
                 },
                 'entity_id': [DEMO_COVER, DEMO_COVER_POS, DEMO_COVER_TILT],
             }
         }}
    ]
}


class TestMultiCover(unittest.TestCase):
    """Test the Multicover component."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop down everthing that was started."""
        self.hass.stop()

    def test_empty_config(self):
        """Test component setup with empty config."""
        with assert_setup_component(1, 'cover'):
            assert setup.setup_component(
                self.hass, 'cover',
                {'cover': {'platform': 'multicover', 'covers': {}}})

    def test_attributes(self):
        """Test state attributes after setup."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG_TILT)

        self.hass.start()
        self.hass.block_till_done()

        state = self.hass.states.get(MULTICOVER)
        attr = state.attributes

        self.assertEqual(state.state, 'open')
        self.assertEqual(attr.get('friendly_name'), "Test Multicover")
        self.assertEqual(attr.get('current_position'), 100)
        self.assertEqual(attr.get('current_tilt_position'), 50)
        self.assertEqual(attr.get('supported_features'), 255)
        self.assertTrue(attr.get('assumed_state'))

    def test_current_cover_position(self):
        """Test different current cover positions."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG)

        self.hass.start()
        self.hass.block_till_done()

        self.assertEqual(self.hass.states.get(MULTICOVER)
                         .attributes.get('current_position'), 100)

        self.hass.states.set(
            DEMO_COVER_POS, 'open',
            {'current_position': 70, 'supported_features': 15})
        mock_state_change_event(self.hass, State(DEMO_COVER_POS, 'open'))
        self.hass.block_till_done()

        self.assertEqual(self.hass.states.get(MULTICOVER)
                         .attributes.get('current_position'), 70)

    def test_current_tilt_position(self):
        """Test different current cover tilt positions."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG_TILT)

        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set(
            'cover.tilt_demo', 'open',
            {'current_tilt_position': 60, 'supported_features': 255})
        self.hass.bus.fire(EVENT_NETWORK_READY)
        mock_state_change_event(self.hass, State(DEMO_COVER, 'open'))
        self.hass.block_till_done()

        self.assertEqual(self.hass.states.get(MULTICOVER)
                         .attributes.get('current_tilt_position'), 100)

        self.hass.states.set(
            'cover.tilt_demo', 'open',
            {'current_tilt_position': 50, 'supported_features': 255})
        mock_state_change_event(self.hass, State(DEMO_COVER, 'open'))
        self.hass.block_till_done()

        self.assertEqual(self.hass.states.get(MULTICOVER)
                         .attributes.get('current_tilt_position'), 50)

    def test_open_covers(self):
        """Test open cover function."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG)

        self.hass.start()
        self.hass.block_till_done()

        cover.open_cover(self.hass, MULTICOVER)
        self.hass.block_till_done()
        for _ in range(10):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(MULTICOVER)
        attr = state.attributes

        self.assertEqual(state.state, 'open')
        self.assertEqual(attr.get('current_position'), 100)

        self.assertEqual(self.hass.states.get(DEMO_COVER).state, 'open')
        self.assertEqual(self.hass.states.get(DEMO_COVER_POS)
                         .attributes.get('current_position'), 100)
        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_position'), 100)

    def test_close_covers(self):
        """Test close cover function."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG)

        self.hass.start()
        self.hass.block_till_done()

        cover.close_cover(self.hass, MULTICOVER)
        self.hass.block_till_done()
        for _ in range(10):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(MULTICOVER)
        attr = state.attributes

        self.assertEqual(state.state, 'closed')
        self.assertEqual(attr.get('current_position'), 0)

        self.assertEqual(self.hass.states.get(DEMO_COVER).state, 'closed')
        self.assertEqual(self.hass.states.get(DEMO_COVER_POS)
                         .attributes.get('current_position'), 0)
        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_position'), 0)

    def test_stop_covers(self):
        """Test stop cover function."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG)

        self.hass.start()
        self.hass.block_till_done()

        cover.open_cover(self.hass, MULTICOVER)
        self.hass.block_till_done()
        future = dt_util.utcnow() + timedelta(seconds=1)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()
        cover.stop_cover(self.hass, MULTICOVER)
        self.hass.block_till_done()
        future = dt_util.utcnow() + timedelta(seconds=1)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()

        state = self.hass.states.get(MULTICOVER)
        attr = state.attributes

        self.assertEqual(state.state, 'open')
        self.assertEqual(attr.get('current_position'), 100)

        self.assertEqual(self.hass.states.get(DEMO_COVER).state, 'open')
        self.assertEqual(self.hass.states.get(DEMO_COVER_POS)
                         .attributes.get('current_position'), 20)
        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_position'), 80)

    def test_set_cover_position(self):
        """Test set cover position function."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG)

        self.hass.start()
        self.hass.block_till_done()

        cover.set_cover_position(self.hass, 50, MULTICOVER)
        self.hass.block_till_done()
        for _ in range(4):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(MULTICOVER)
        attr = state.attributes

        self.assertEqual(state.state, 'open')
        self.assertEqual(attr.get('current_position'), 50)

        self.assertEqual(self.hass.states.get(DEMO_COVER).state, 'closed')
        self.assertEqual(self.hass.states.get(DEMO_COVER_POS)
                         .attributes.get('current_position'), 50)
        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_position'), 50)

    def test_open_tilts(self):
        """Test open tilt function."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG_TILT)

        self.hass.start()
        self.hass.block_till_done()

        cover.open_cover_tilt(self.hass, MULTICOVER)
        self.hass.block_till_done()
        for _ in range(5):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(MULTICOVER)
        attr = state.attributes

        self.assertEqual(state.state, 'open')
        self.assertEqual(attr.get('current_tilt_position'), 100)

        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_tilt_position'), 100)

    def test_close_tilts(self):
        """Test close tilt function."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG_TILT)

        self.hass.start()
        self.hass.block_till_done()

        cover.close_cover_tilt(self.hass, MULTICOVER)
        self.hass.block_till_done()
        for _ in range(5):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(MULTICOVER)
        attr = state.attributes

        self.assertEqual(state.state, 'open')
        self.assertEqual(attr.get('current_tilt_position'), 0)

        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_tilt_position'), 0)

    def test_stop_tilts(self):
        """Test stop tilts function."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG_TILT)

        self.hass.start()
        self.hass.block_till_done()

        cover.open_cover_tilt(self.hass, MULTICOVER)
        self.hass.block_till_done()
        future = dt_util.utcnow() + timedelta(seconds=1)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()
        cover.stop_cover_tilt(self.hass, MULTICOVER)
        self.hass.block_till_done()
        future = dt_util.utcnow() + timedelta(seconds=1)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()

        state = self.hass.states.get(MULTICOVER)
        attr = state.attributes

        self.assertEqual(state.state, 'open')
        self.assertEqual(attr.get('current_tilt_position'), 60)

        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_tilt_position'), 60)

    def test_set_tilt_positions(self):
        """Test set tilt position function."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover', CONFIG_TILT)

        self.hass.start()
        self.hass.block_till_done()

        cover.set_cover_tilt_position(self.hass, 80, MULTICOVER)
        self.hass.block_till_done()
        for _ in range(3):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(MULTICOVER)
        attr = state.attributes

        self.assertEqual(state.state, 'open')
        self.assertEqual(attr.get('current_tilt_position'), 80)

        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_tilt_position'), 80)

    def test_winter_protection_false(self):
        """Test winter protection feature with temperature over limit."""
        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover',
                                         CONFIG_WINTERPROTECTION)

        self.hass.start()
        self.hass.block_till_done()

        self.hass.states.set('sensor.temperature', 10)

        cover.open_cover(self.hass, MULTICOVER)
        self.hass.block_till_done()
        for _ in range(10):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(MULTICOVER)
        attr = state.attributes

        self.assertEqual(state.state, 'open')
        self.assertEqual(attr.get('current_position'), 100)

        self.assertEqual(self.hass.states.get(DEMO_COVER).state, 'open')
        self.assertEqual(self.hass.states.get(DEMO_COVER_POS)
                         .attributes.get('current_position'), 100)
        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_position'), 100)

    def test_winter_protection_true(self):
        """Test winter protection feature with temperature under limit."""
        self.hass.states.set('sensor.temperature', 2)

        with assert_setup_component(2, 'cover'):
            assert setup.setup_component(self.hass, 'cover',
                                         CONFIG_WINTERPROTECTION)

        self.hass.start()
        self.hass.block_till_done()

        cover.close_cover(self.hass, MULTICOVER)
        self.hass.block_till_done()
        for _ in range(10):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(MULTICOVER)
        attr = state.attributes

        self.assertEqual(state.state, 'open')
        self.assertEqual(attr.get('current_position'), 10)

        self.assertEqual(self.hass.states.get(DEMO_COVER).state, 'closed')
        self.assertEqual(self.hass.states.get(DEMO_COVER_POS)
                         .attributes.get('current_position'), 10)
        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_position'), 10)

        self.hass.states.set('sensor.temperature', 0)

        cover.open_cover(self.hass, MULTICOVER)
        self.hass.block_till_done()
        for _ in range(10):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(MULTICOVER)
        attr = state.attributes

        self.assertEqual(state.state, 'open')
        self.assertEqual(attr.get('current_position'), 90)

        self.assertEqual(self.hass.states.get(DEMO_COVER).state, 'open')
        self.assertEqual(self.hass.states.get(DEMO_COVER_POS)
                         .attributes.get('current_position'), 90)
        self.assertEqual(self.hass.states.get(DEMO_COVER_TILT)
                         .attributes.get('current_position'), 90)

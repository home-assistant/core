"""The tests for the Demo cover platform."""
import unittest
from datetime import timedelta
import homeassistant.util.dt as dt_util

from homeassistant.bootstrap import setup_component
from homeassistant.components import cover
from tests.common import get_test_home_assistant, fire_time_changed

ENTITY_COVER = 'cover.living_room_window'


class TestCoverDemo(unittest.TestCase):
    """Test the Demo cover."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.assertTrue(setup_component(self.hass, cover.DOMAIN, {'cover': {
            'platform': 'demo',
        }}))

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_close_cover(self):
        """Test closing the cover."""
        state = self.hass.states.get(ENTITY_COVER)
        self.assertEqual(70, state.attributes.get('current_position'))
        cover.close_cover(self.hass, ENTITY_COVER)
        self.hass.block_till_done()
        for _ in range(7):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(ENTITY_COVER)
        self.assertEqual(0, state.attributes.get('current_position'))

    def test_open_cover(self):
        """Test opening the cover."""
        state = self.hass.states.get(ENTITY_COVER)
        self.assertEqual(70, state.attributes.get('current_position'))
        cover.open_cover(self.hass, ENTITY_COVER)
        self.hass.block_till_done()
        for _ in range(7):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(ENTITY_COVER)
        self.assertEqual(100, state.attributes.get('current_position'))

    def test_set_cover_position(self):
        """Test moving the cover to a specific position."""
        state = self.hass.states.get(ENTITY_COVER)
        self.assertEqual(70, state.attributes.get('current_position'))
        cover.set_cover_position(self.hass, 10, ENTITY_COVER)
        self.hass.block_till_done()
        for _ in range(6):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(ENTITY_COVER)
        self.assertEqual(10, state.attributes.get('current_position'))

    def test_stop_cover(self):
        """Test stopping the cover."""
        state = self.hass.states.get(ENTITY_COVER)
        self.assertEqual(70, state.attributes.get('current_position'))
        cover.open_cover(self.hass, ENTITY_COVER)
        self.hass.block_till_done()
        future = dt_util.utcnow() + timedelta(seconds=1)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()
        cover.stop_cover(self.hass, ENTITY_COVER)
        self.hass.block_till_done()
        fire_time_changed(self.hass, future)
        state = self.hass.states.get(ENTITY_COVER)
        self.assertEqual(80, state.attributes.get('current_position'))

    def test_close_cover_tilt(self):
        """Test closing the cover tilt."""
        state = self.hass.states.get(ENTITY_COVER)
        self.assertEqual(50, state.attributes.get('current_tilt_position'))
        cover.close_cover_tilt(self.hass, ENTITY_COVER)
        self.hass.block_till_done()
        for _ in range(7):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(ENTITY_COVER)
        self.assertEqual(0, state.attributes.get('current_tilt_position'))

    def test_open_cover_tilt(self):
        """Test opening the cover tilt."""
        state = self.hass.states.get(ENTITY_COVER)
        self.assertEqual(50, state.attributes.get('current_tilt_position'))
        cover.open_cover_tilt(self.hass, ENTITY_COVER)
        self.hass.block_till_done()
        for _ in range(7):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(ENTITY_COVER)
        self.assertEqual(100, state.attributes.get('current_tilt_position'))

    def test_set_cover_tilt_position(self):
        """Test moving the cover til to a specific position."""
        state = self.hass.states.get(ENTITY_COVER)
        self.assertEqual(50, state.attributes.get('current_tilt_position'))
        cover.set_cover_tilt_position(self.hass, 90, ENTITY_COVER)
        self.hass.block_till_done()
        for _ in range(7):
            future = dt_util.utcnow() + timedelta(seconds=1)
            fire_time_changed(self.hass, future)
            self.hass.block_till_done()

        state = self.hass.states.get(ENTITY_COVER)
        self.assertEqual(90, state.attributes.get('current_tilt_position'))

    def test_stop_cover_tilt(self):
        """Test stopping the cover tilt."""
        state = self.hass.states.get(ENTITY_COVER)
        self.assertEqual(50, state.attributes.get('current_tilt_position'))
        cover.close_cover_tilt(self.hass, ENTITY_COVER)
        self.hass.block_till_done()
        future = dt_util.utcnow() + timedelta(seconds=1)
        fire_time_changed(self.hass, future)
        self.hass.block_till_done()
        cover.stop_cover_tilt(self.hass, ENTITY_COVER)
        self.hass.block_till_done()
        fire_time_changed(self.hass, future)
        state = self.hass.states.get(ENTITY_COVER)
        self.assertEqual(40, state.attributes.get('current_tilt_position'))

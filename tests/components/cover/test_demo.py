"""The tests for the Demo cover platform."""
import unittest
import homeassistant.util.dt as dt_util

from homeassistant.components.cover import demo
from tests.common import fire_time_changed, get_test_home_assistant


class TestCoverDemo(unittest.TestCase):
    """Test the Demo cover."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_close_cover(self):
        """Test closing the cover."""
        entity = demo.DemoCover(self.hass, 'test', 100, None)
        entity.close_cover()

        fire_time_changed(self.hass, dt_util.utcnow())
        self.hass.pool.block_till_done()
        self.assertEqual(90, entity.current_cover_position)

    def test_open_cover(self):
        """Test opening the cover."""
        entity = demo.DemoCover(self.hass, 'test', 0, None)
        entity.open_cover()

        fire_time_changed(self.hass, dt_util.utcnow())
        self.hass.pool.block_till_done()
        self.assertEqual(10, entity.current_cover_position)

    def test_set_cover_position(self):
        """Test moving the cover to a specific position."""
        entity = demo.DemoCover(self.hass, 'test', 0, None)
        entity.set_cover_position(10)

        fire_time_changed(self.hass, dt_util.utcnow())
        self.hass.pool.block_till_done()
        self.assertEqual(10, entity.current_cover_position)

    def test_stop_cover(self):
        """Test stopping the cover."""
        entity = demo.DemoCover(self.hass, 'test', 0, None)
        entity.open_cover()
        entity.stop_cover()

        fire_time_changed(self.hass, dt_util.utcnow())
        self.hass.pool.block_till_done()
        self.assertEqual(0, entity.current_cover_position)

    def test_close_cover_tilt(self):
        """Test closing the cover tilt."""
        entity = demo.DemoCover(self.hass, 'test', None, 100)
        entity.close_cover_tilt()

        fire_time_changed(self.hass, dt_util.utcnow())
        self.hass.pool.block_till_done()
        self.assertEqual(90, entity.current_cover_tilt_position)

    def test_open_cover_tilt(self):
        """Test opening the cover tilt."""
        entity = demo.DemoCover(self.hass, 'test', None, 0)
        entity.open_cover_tilt()

        fire_time_changed(self.hass, dt_util.utcnow())
        self.hass.pool.block_till_done()
        self.assertEqual(10, entity.current_cover_tilt_position)

    def test_set_cover_tilt_position(self):
        """Test moving the cover til to a specific position."""
        entity = demo.DemoCover(self.hass, 'test', None, 0)
        entity.set_cover_tilt_position(10)

        fire_time_changed(self.hass, dt_util.utcnow())
        self.hass.pool.block_till_done()
        self.assertEqual(10, entity.current_cover_tilt_position)

    def test_stop_cover_tilt(self):
        """Test stopping the cover tilt."""
        entity = demo.DemoCover(self.hass, 'test', None, 0)
        entity.open_cover_tilt()
        entity.stop_cover_tilt()

        fire_time_changed(self.hass, dt_util.utcnow())
        self.hass.pool.block_till_done()
        self.assertEqual(0, entity.current_cover_tilt_position)

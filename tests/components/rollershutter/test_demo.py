"""The tests for the Demo roller shutter platform."""
import unittest
import homeassistant.util.dt as dt_util

from homeassistant.components.rollershutter import demo
from tests.common import fire_time_changed, get_test_home_assistant


class TestRollershutterDemo(unittest.TestCase):
    """Test the Demo roller shutter."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_move_up(self):
        """Test moving the rollershutter up."""
        entity = demo.DemoRollershutter(self.hass, 'test', 100)
        entity.move_up()

        fire_time_changed(self.hass, dt_util.utcnow())
        self.hass.block_till_done()
        self.assertEqual(90, entity.current_position)

    def test_move_down(self):
        """Test moving the rollershutter down."""
        entity = demo.DemoRollershutter(self.hass, 'test', 0)
        entity.move_down()

        fire_time_changed(self.hass, dt_util.utcnow())
        self.hass.block_till_done()
        self.assertEqual(10, entity.current_position)

    def test_move_position(self):
        """Test moving the rollershutter to a specific position."""
        entity = demo.DemoRollershutter(self.hass, 'test', 0)
        entity.move_position(10)

        fire_time_changed(self.hass, dt_util.utcnow())
        self.hass.block_till_done()
        self.assertEqual(10, entity.current_position)

    def test_stop(self):
        """Test stopping the rollershutter."""
        entity = demo.DemoRollershutter(self.hass, 'test', 0)
        entity.move_down()
        entity.stop()

        fire_time_changed(self.hass, dt_util.utcnow())
        self.hass.block_till_done()
        self.assertEqual(0, entity.current_position)

"""Test Times of the Day Binary Sensor."""
import unittest
from unittest import mock

from tests.common import (
    get_test_home_assistant, assert_setup_component, async_fire_time_changed)

class TestBinarySensorTod(unittest.TestCase):
    """Test for Binary sensor tod platform."""

    hass = None
    # pylint: disable=invalid-name

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()
    
    def test_setup(self):
        return True

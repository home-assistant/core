"""The tests for the Introduction component."""
import unittest

from homeassistant.components import introduction

from tests.common import get_test_home_assistant


class TestIntroduction(unittest.TestCase):
    """Test Introduction."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup(self):
        """Test introduction setup."""
        self.assertTrue(introduction.setup(self.hass, {}))

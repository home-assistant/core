"""The tests for the Introduction component."""
import unittest

from homeassistant.setup import setup_component
from homeassistant.components import introduction

from tests.common import get_test_home_assistant


class TestIntroduction(unittest.TestCase):
    """Test Introduction."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup(self):
        """Test introduction setup."""
        assert setup_component(self.hass, introduction.DOMAIN, {})

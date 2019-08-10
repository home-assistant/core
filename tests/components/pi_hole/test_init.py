"""Test pi_hole component."""

import unittest

from homeassistant import setup
from homeassistant.components import pi_hole
from homeassistant.const import CONF_MONITORED_CONDITIONS

from tests.common import get_test_home_assistant


class TestComponentPiHole(unittest.TestCase):
    """Test the pi_hole component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_no_config(self):
        """Test a successful setup with no configuration."""
        config = {CONF_MONITORED_CONDITIONS: []}
        assert setup.setup_component(self.hass, pi_hole.DOMAIN, {"pi_hole": config})

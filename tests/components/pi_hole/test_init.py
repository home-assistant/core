"""Test pi_hole component."""

import unittest

from homeassistant.components.pi_hole import sensor as pi_hole
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.util.async_ import run_coroutine_threadsafe

from tests.common import get_test_home_assistant


def mock_async_add_entities(sensors, enable):
    """Mock function."""
    return


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
        assert not run_coroutine_threadsafe(
            pi_hole.async_setup_platform(self.hass, config, mock_async_add_entities),
            self.hass.loop,
        ).result()

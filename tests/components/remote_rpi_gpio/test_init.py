"""test setup."""

import unittest

import homeassistant.components.remote_rpi_gpio as remote_rpi_gpio
from homeassistant.setup import setup_component

from tests.common import assert_setup_component, get_test_home_assistant


class TestRemoteRpiGpioSetup(unittest.TestCase):
    """Test the remote module."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_empty_setup(self):
        """Test setup with configuration missing required entries."""
        with assert_setup_component(0):
            assert setup_component(self.hass, remote_rpi_gpio.DOMAIN, {})

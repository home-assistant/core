"""The tests for the opnsense device tracker platform."""

import unittest
from unittest import mock

from homeassistant.components import opnsense
from homeassistant.components.opnsense import CONF_API_SECRET, DOMAIN, OPNSENSE_DATA
from homeassistant.const import CONF_URL, CONF_API_KEY, CONF_VERIFY_SSL
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant


class TestOpnSenseDeviceTrackerSetup(unittest.TestCase):
    """Test opnsense device tracker setup."""

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch.object(opnsense, 'diagnostics')
    def test_get_scanner(self, pyopnsense_mock):
        """Test creating an opnsense scanner."""
        result = setup_component(
            self.hass,
            DOMAIN,
            {
                DOMAIN: {
                    CONF_URL: "https://fake_host_fun/api",
                    CONF_API_KEY: "fake_key",
                    CONF_API_SECRET: "fake_secret",
                    CONF_VERIFY_SSL: False,
                }
            },
        )
        assert result
        assert self.hass.data[OPNSENSE_DATA] is not None
        assert pyopnsense_mock.has_calls()

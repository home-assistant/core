"""The tests for the Homematic notification platform."""

import unittest

import homeassistant.components.notify as notify_comp
from homeassistant.setup import setup_component

from tests.common import assert_setup_component, get_test_home_assistant


class TestHomematicNotify(unittest.TestCase):
    """Test the Homematic notifications."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_setup_full(self):
        """Test valid configuration."""
        setup_component(
            self.hass,
            "homematic",
            {"homematic": {"hosts": {"ccu2": {"host": "127.0.0.1"}}}},
        )
        with assert_setup_component(1) as handle_config:
            assert setup_component(
                self.hass,
                "notify",
                {
                    "notify": {
                        "name": "test",
                        "platform": "homematic",
                        "address": "NEQXXXXXXX",
                        "channel": 2,
                        "param": "SUBMIT",
                        "value": "1,1,108000,2",
                        "interface": "my-interface",
                    }
                },
            )
        assert handle_config[notify_comp.DOMAIN]

    def test_setup_without_optional(self):
        """Test valid configuration without optional."""
        setup_component(
            self.hass,
            "homematic",
            {"homematic": {"hosts": {"ccu2": {"host": "127.0.0.1"}}}},
        )
        with assert_setup_component(1) as handle_config:
            assert setup_component(
                self.hass,
                "notify",
                {
                    "notify": {
                        "name": "test",
                        "platform": "homematic",
                        "address": "NEQXXXXXXX",
                        "channel": 2,
                        "param": "SUBMIT",
                        "value": "1,1,108000,2",
                    }
                },
            )
        assert handle_config[notify_comp.DOMAIN]

    def test_bad_config(self):
        """Test invalid configuration."""
        config = {notify_comp.DOMAIN: {"name": "test", "platform": "homematic"}}
        with assert_setup_component(0) as handle_config:
            assert setup_component(self.hass, notify_comp.DOMAIN, config)
        assert not handle_config[notify_comp.DOMAIN]

"""The tests for the Demo component."""
import json
import os
import unittest

from homeassistant.bootstrap import setup_component
from homeassistant.components import demo, device_tracker
from homeassistant.remote import JSONEncoder

from tests.common import mock_http_component, get_test_home_assistant


class TestDemo(unittest.TestCase):
    """Test the Demo component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_http_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

        try:
            os.remove(self.hass.config.path(device_tracker.YAML_DEVICES))
        except FileNotFoundError:
            pass

    def test_if_demo_state_shows_by_default(self):
        """Test if demo state shows if we give no configuration."""
        setup_component(self.hass, demo.DOMAIN, {demo.DOMAIN: {}})

        self.assertIsNotNone(self.hass.states.get('a.Demo_Mode'))

    def test_hiding_demo_state(self):
        """Test if you can hide the demo card."""
        setup_component(self.hass, demo.DOMAIN, {
            demo.DOMAIN: {'hide_demo_state': 1}})

        self.assertIsNone(self.hass.states.get('a.Demo_Mode'))

    def test_all_entities_can_be_loaded_over_json(self):
        """Test if you can hide the demo card."""
        setup_component(self.hass, demo.DOMAIN, {
            demo.DOMAIN: {'hide_demo_state': 1}})

        try:
            json.dumps(self.hass.states.all(), cls=JSONEncoder)
        except Exception:
            self.fail('Unable to convert all demo entities to JSON. '
                      'Wrong data in state machine!')

"""The tests for the Configurator component."""
# pylint: disable=too-many-public-methods,protected-access
import unittest

import homeassistant.components.configurator as configurator
from homeassistant.const import EVENT_TIME_CHANGED, ATTR_FRIENDLY_NAME

from tests.common import get_test_home_assistant


class TestConfigurator(unittest.TestCase):
    """Test the Configurator component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_request_least_info(self):
        """Test request config with least amount of data."""
        request_id = configurator.request_config(
            self.hass, "Test Request", lambda _: None)

        self.assertEqual(
            1, len(self.hass.services.services.get(configurator.DOMAIN, [])),
            "No new service registered")

        states = self.hass.states.all()

        self.assertEqual(1, len(states), "Expected a new state registered")

        state = states[0]

        self.assertEqual(configurator.STATE_CONFIGURE, state.state)
        self.assertEqual(
            request_id, state.attributes.get(configurator.ATTR_CONFIGURE_ID))

    def test_request_all_info(self):
        """Test request config with all possible info."""
        exp_attr = {
            ATTR_FRIENDLY_NAME: "Test Request",
            configurator.ATTR_DESCRIPTION: "config description",
            configurator.ATTR_DESCRIPTION_IMAGE: "config image url",
            configurator.ATTR_SUBMIT_CAPTION: "config submit caption",
            configurator.ATTR_FIELDS: [],
            configurator.ATTR_CONFIGURE_ID: configurator.request_config(
                self.hass, "Test Request", lambda _: None,
                "config description", "config image url",
                "config submit caption"
            )
        }

        states = self.hass.states.all()
        self.assertEqual(1, len(states))
        state = states[0]

        self.assertEqual(configurator.STATE_CONFIGURE, state.state)
        assert exp_attr == dict(state.attributes)

    def test_callback_called_on_configure(self):
        """Test if our callback gets called when configure service called."""
        calls = []
        request_id = configurator.request_config(
            self.hass, "Test Request", lambda _: calls.append(1))

        self.hass.services.call(
            configurator.DOMAIN, configurator.SERVICE_CONFIGURE,
            {configurator.ATTR_CONFIGURE_ID: request_id})

        self.hass.block_till_done()
        self.assertEqual(1, len(calls), "Callback not called")

    def test_state_change_on_notify_errors(self):
        """Test state change on notify errors."""
        request_id = configurator.request_config(
            self.hass, "Test Request", lambda _: None)
        error = "Oh no bad bad bad"
        configurator.notify_errors(request_id, error)

        state = self.hass.states.all()[0]
        self.assertEqual(error, state.attributes.get(configurator.ATTR_ERRORS))

    def test_notify_errors_fail_silently_on_bad_request_id(self):
        """Test if notify errors fails silently with a bad request id."""
        configurator.notify_errors(2015, "Try this error")

    def test_request_done_works(self):
        """Test if calling request done works."""
        request_id = configurator.request_config(
            self.hass, "Test Request", lambda _: None)
        configurator.request_done(request_id)
        self.assertEqual(1, len(self.hass.states.all()))

        self.hass.bus.fire(EVENT_TIME_CHANGED)
        self.hass.block_till_done()
        self.assertEqual(0, len(self.hass.states.all()))

    def test_request_done_fail_silently_on_bad_request_id(self):
        """Test that request_done fails silently with a bad request id."""
        configurator.request_done(2016)

"""The tests for the Configurator component."""
# pylint: disable=protected-access
import unittest

import homeassistant.components.configurator as configurator
from homeassistant.const import ATTR_FRIENDLY_NAME, EVENT_TIME_CHANGED

from tests.common import get_test_home_assistant


class TestConfigurator(unittest.TestCase):
    """Test the Configurator component."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.addCleanup(self.hass.stop)

    def test_request_least_info(self):
        """Test request config with least amount of data."""
        request_id = configurator.request_config(
            self.hass, "Test Request", lambda _: None
        )

        assert 1 == len(
            self.hass.services.services.get(configurator.DOMAIN, [])
        ), "No new service registered"

        states = self.hass.states.all()

        assert 1 == len(states), "Expected a new state registered"

        state = states[0]

        assert configurator.STATE_CONFIGURE == state.state
        assert request_id == state.attributes.get(configurator.ATTR_CONFIGURE_ID)

    def test_request_all_info(self):
        """Test request config with all possible info."""
        exp_attr = {
            ATTR_FRIENDLY_NAME: "Test Request",
            configurator.ATTR_DESCRIPTION: """config description

[link name](link url)

![Description image](config image url)""",
            configurator.ATTR_SUBMIT_CAPTION: "config submit caption",
            configurator.ATTR_FIELDS: [],
            configurator.ATTR_ENTITY_PICTURE: "config entity picture",
            configurator.ATTR_CONFIGURE_ID: configurator.request_config(
                self.hass,
                name="Test Request",
                callback=lambda _: None,
                description="config description",
                description_image="config image url",
                submit_caption="config submit caption",
                fields=None,
                link_name="link name",
                link_url="link url",
                entity_picture="config entity picture",
            ),
        }

        states = self.hass.states.all()
        assert 1 == len(states)
        state = states[0]

        assert configurator.STATE_CONFIGURE == state.state
        assert exp_attr == state.attributes

    def test_callback_called_on_configure(self):
        """Test if our callback gets called when configure service called."""
        calls = []
        request_id = configurator.request_config(
            self.hass, "Test Request", lambda _: calls.append(1)
        )

        self.hass.services.call(
            configurator.DOMAIN,
            configurator.SERVICE_CONFIGURE,
            {configurator.ATTR_CONFIGURE_ID: request_id},
        )

        self.hass.block_till_done()
        assert 1 == len(calls), "Callback not called"

    def test_state_change_on_notify_errors(self):
        """Test state change on notify errors."""
        request_id = configurator.request_config(
            self.hass, "Test Request", lambda _: None
        )
        error = "Oh no bad bad bad"
        configurator.notify_errors(self.hass, request_id, error)

        state = self.hass.states.all()[0]
        assert error == state.attributes.get(configurator.ATTR_ERRORS)

    def test_notify_errors_fail_silently_on_bad_request_id(self):
        """Test if notify errors fails silently with a bad request id."""
        configurator.notify_errors(self.hass, 2015, "Try this error")

    def test_request_done_works(self):
        """Test if calling request done works."""
        request_id = configurator.request_config(
            self.hass, "Test Request", lambda _: None
        )
        configurator.request_done(self.hass, request_id)
        assert 1 == len(self.hass.states.all())

        self.hass.bus.fire(EVENT_TIME_CHANGED)
        self.hass.block_till_done()
        assert 0 == len(self.hass.states.all())

    def test_request_done_fail_silently_on_bad_request_id(self):
        """Test that request_done fails silently with a bad request id."""
        configurator.request_done(self.hass, 2016)

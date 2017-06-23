"""The tests for the textfile conversation platform."""
from unittest.mock import patch, mock_open

from homeassistant.setup import setup_component

from tests.common import (
    get_test_home_assistant, assert_setup_component)

from homeassistant.components import conversation


class TestTextfileConversationPlatform(object):
    """Test the textfile conversation component."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.tmppath = '/tmp/this_will_be_mocked'

    def teardown_method(self):
        """Remove created file."""
        self.hass.stop()

    def test_setup_component(self):
        """Test setup component."""
        config = {
            conversation.DOMAIN: {
                "platform": "textfile",
                "path": self.tmppath
            }
        }

        with assert_setup_component(1, conversation.DOMAIN):
            component = setup_component(self.hass, conversation.DOMAIN, config)

        return component

    def test_service_process(self):
        """Test service process conversation text."""
        config = {
            conversation.DOMAIN: {
                "platform": "textfile",
                "path": self.tmppath
            }
        }

        with assert_setup_component(1, conversation.DOMAIN):
            setup_component(self.hass, conversation.DOMAIN, config)

        m = mock_open()
        with patch('builtins.open', m):

            self.hass.services.call(conversation.DOMAIN, 'process', {
                conversation.ATTR_TEXT: "turn on the light",
            })
            self.hass.block_till_done()

        # Check that the file write method was called
        m.assert_called_once_with(self.tmppath, "a")
        m().write.assert_called_once_with("turn on the light\n")

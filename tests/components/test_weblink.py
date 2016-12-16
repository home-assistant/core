"""The tests for the weblink component."""
import unittest

from homeassistant.bootstrap import setup_component
from homeassistant.components import weblink
from homeassistant import bootstrap

from tests.common import get_test_home_assistant


class TestComponentWeblink(unittest.TestCase):
    """Test the Weblink component."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_bad_config(self):
        """Test if new entity is created."""
        self.assertFalse(bootstrap.setup_component(self.hass, 'weblink', {
            'weblink': {
                'entities': [{}],
            }
        }))

    def test_entities_get_created(self):
        """Test if new entity is created."""
        self.assertTrue(setup_component(self.hass, weblink.DOMAIN, {
            weblink.DOMAIN: {
                'entities': [
                    {
                        weblink.CONF_NAME: 'My router',
                        weblink.CONF_URL: 'http://127.0.0.1/'
                    },
                ]
            }
        }))

        state = self.hass.states.get('weblink.my_router')

        assert state is not None
        assert state.state == 'http://127.0.0.1/'

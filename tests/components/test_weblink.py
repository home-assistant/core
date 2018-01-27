"""The tests for the weblink component."""
import unittest

from homeassistant.setup import setup_component
from homeassistant.components import weblink

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
        self.assertFalse(setup_component(self.hass, 'weblink', {
            'weblink': {
                'entities': [{}],
            }
        }))

    def test_bad_config_relative_url(self):
        """Test if new entity is created."""
        self.assertFalse(setup_component(self.hass, 'weblink', {
            'weblink': {
                'entities': [
                    {
                        weblink.CONF_NAME: 'My router',
                        weblink.CONF_URL: '../states/group.bla'
                    },
                ],
            }
        }))

    def test_bad_config_relative_file(self):
        """Test if new entity is created."""
        self.assertFalse(setup_component(self.hass, 'weblink', {
            'weblink': {
                'entities': [
                    {
                        weblink.CONF_NAME: 'My group',
                        weblink.CONF_URL: 'group.bla'
                    },
                ],
            }
        }))

    def test_good_config_absolute_path(self):
        """Test if new entity is created."""
        self.assertTrue(setup_component(self.hass, 'weblink', {
            'weblink': {
                'entities': [
                    {
                        weblink.CONF_NAME: 'My second URL',
                        weblink.CONF_URL: '/states/group.bla'
                    },
                ],
            }
        }))

    def test_good_config_path_short(self):
        """Test if new entity is created."""
        self.assertTrue(setup_component(self.hass, 'weblink', {
            'weblink': {
                'entities': [
                    {
                        weblink.CONF_NAME: 'My third URL',
                        weblink.CONF_URL: '/states'
                    },
                ],
            }
        }))

    def test_good_config_path_directory(self):
        """Test if new entity is created."""
        self.assertTrue(setup_component(self.hass, 'weblink', {
            'weblink': {
                'entities': [
                    {
                        weblink.CONF_NAME: 'My last URL',
                        weblink.CONF_URL: '/states/bla/'
                    },
                ],
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

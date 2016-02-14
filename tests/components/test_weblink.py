"""
tests.components.test_weblink
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests weblink component.
"""
import unittest

from homeassistant.components import weblink

from tests.common import get_test_home_assistant


class TestComponentWeblink(unittest.TestCase):
    """ Tests homeassistant.components.history module. """

    def setUp(self):
        """ Test setup method. """
        self.hass = get_test_home_assistant()

    def tearDown(self):
        self.hass.stop()

    def test_entities_get_created(self):
        self.assertTrue(weblink.setup(self.hass, {
            weblink.DOMAIN: {
                'entities': [
                    {
                        weblink.ATTR_NAME: 'My router',
                        weblink.ATTR_URL: 'http://127.0.0.1/'
                    },
                    {}
                ]
            }
        }))

        state = self.hass.states.get('weblink.my_router')

        assert state is not None
        assert state.state == 'http://127.0.0.1/'

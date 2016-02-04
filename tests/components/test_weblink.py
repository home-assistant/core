# -*- coding: utf-8 -*-
import unittest

import homeassistant.core as ha
from homeassistant.components import weblink


class TestComponentHistory(unittest.TestCase):
    """ Tests homeassistant.components.history module. """

    def setUp(self):
        """ Test setup method. """
        self.hass = ha.HomeAssistant()

    def tearDown(self):
        self.hass.stop()

    def test_setup(self):
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

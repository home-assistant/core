"""
homeassistant.test
~~~~~~~~~~~~~~~~~~

Provides tests to verify that Home Assistant modules do what they should do.

"""
# pylint: disable=too-many-public-methods
import unittest

import homeassistant as ha
import homeassistant.loader as loader
import homeassistant.components.http as http


class TestLoader(unittest.TestCase):
    """ Test the loader module. """
    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()
        loader.prepare(self.hass)

    def test_get_component(self):
        """ Test if get_component works. """
        self.assertEqual(http, loader.get_component('http'))

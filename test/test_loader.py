"""
test.test_loader
~~~~~~~~~~~~~~~~~~

Provides tests to verify that we can load components.
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

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass._pool.stop()

    def test_get_component(self):
        """ Test if get_component works. """
        self.assertEqual(http, loader.get_component('http'))

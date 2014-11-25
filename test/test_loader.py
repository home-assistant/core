"""
test.test_loader
~~~~~~~~~~~~~~~~~~

Provides tests to verify that we can load components.
"""
# pylint: disable=too-many-public-methods,protected-access
import unittest

import homeassistant as ha
import homeassistant.loader as loader
import homeassistant.components.http as http

from mock import switch_platform


class TestLoader(unittest.TestCase):
    """ Test the loader module. """
    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()
        loader.prepare(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass._pool.stop()

    def test_set_component(self):
        """ Test if set_component works. """
        loader.set_component('switch.test', switch_platform)

        self.assertEqual(
            switch_platform, loader.get_component('switch.test'))

    def test_get_component(self):
        """ Test if get_component works. """
        self.assertEqual(http, loader.get_component('http'))

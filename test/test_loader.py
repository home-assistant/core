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

import mock_toggledevice_platform
from helper import get_test_home_assistant


class TestLoader(unittest.TestCase):
    """ Test the loader module. """
    def setUp(self):  # pylint: disable=invalid-name
        self.hass = get_test_home_assistant()
        loader.prepare(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass._pool.stop()

    def test_set_component(self):
        """ Test if set_component works. """
        loader.set_component('switch.test', mock_toggledevice_platform)

        self.assertEqual(
            mock_toggledevice_platform, loader.get_component('switch.test'))

    def test_get_component(self):
        """ Test if get_component works. """
        self.assertEqual(http, loader.get_component('http'))

        self.assertIsNotNone(loader.get_component('custom_one'))

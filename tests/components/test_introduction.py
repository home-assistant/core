"""
tests.components.introduction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test introduction.

This test is primarily to ensure that default components don't crash HASS.
"""

import unittest

import homeassistant.core as ha
from homeassistant.components import introduction


class TestIntroduction(unittest.TestCase):
    """ Test Introduction. """

    def setUp(self):
        self.hass = ha.HomeAssistant()

    def tearDown(self):
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_setup(self):
        """ Test Introduction setup """
        self.assertTrue(introduction.setup(self.hass, {}))

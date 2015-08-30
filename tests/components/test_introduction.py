"""
tests.components.test_introduction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests Introduction component.
"""
# pylint: disable=too-many-public-methods,protected-access
import unittest

import homeassistant.core as ha
import homeassistant.components.introduction as introduction


class TestIntroduction(unittest.TestCase):
    """ Test the introduction module. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_setup(self):
        """ Create introduction entity. """
        introduction.setup(self.hass)

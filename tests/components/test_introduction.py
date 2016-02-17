"""
tests.components.test_introduction
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Test introduction.
"""
import unittest

from homeassistant.components import introduction

from tests.common import get_test_home_assistant


class TestIntroduction(unittest.TestCase):
    """ Test Introduction. """

    def setUp(self):
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_setup(self):
        """ Test Introduction setup """
        self.assertTrue(introduction.setup(self.hass, {}))

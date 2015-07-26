"""
Tests Home Assistant color util methods.
"""
import unittest
import homeassistant.util.color as color_util


class TestColorUtil(unittest.TestCase):
    # pylint: disable=invalid-name
    def test_color_RGB_to_xy(self):
        """ Test color_RGB_to_xy. """
        self.assertEqual((0, 0), color_util.color_RGB_to_xy(0, 0, 0))
        self.assertEqual((0.3127159072215825, 0.3290014805066623),
                         color_util.color_RGB_to_xy(255, 255, 255))

        self.assertEqual((0.15001662234042554, 0.060006648936170214),
                         color_util.color_RGB_to_xy(0, 0, 255))

        self.assertEqual((0.3, 0.6), color_util.color_RGB_to_xy(0, 255, 0))

        self.assertEqual((0.6400744994567747, 0.3299705106316933),
                         color_util.color_RGB_to_xy(255, 0, 0))

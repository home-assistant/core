"""Test Home Assistant color util methods."""
import unittest
import homeassistant.util.color as color_util


class TestColorUtil(unittest.TestCase):
    """Test color util methods."""

    # pylint: disable=invalid-name
    def test_color_RGB_to_xy(self):
        """Test color_RGB_to_xy."""
        self.assertEqual((0, 0), color_util.color_RGB_to_xy(0, 0, 0))
        self.assertEqual((0.3127159072215825, 0.3290014805066623),
                         color_util.color_RGB_to_xy(255, 255, 255))

        self.assertEqual((0.15001662234042554, 0.060006648936170214),
                         color_util.color_RGB_to_xy(0, 0, 255))

        self.assertEqual((0.3, 0.6), color_util.color_RGB_to_xy(0, 255, 0))

        self.assertEqual((0.6400744994567747, 0.3299705106316933),
                         color_util.color_RGB_to_xy(255, 0, 0))

    def test_color_xy_brightness_to_RGB(self):
        """Test color_RGB_to_xy."""
        self.assertEqual((0, 0, 0),
                         color_util.color_xy_brightness_to_RGB(1, 1, 0))

        self.assertEqual((255, 235, 214),
                         color_util.color_xy_brightness_to_RGB(.35, .35, 255))

        self.assertEqual((255, 0, 45),
                         color_util.color_xy_brightness_to_RGB(1, 0, 255))

        self.assertEqual((0, 255, 0),
                         color_util.color_xy_brightness_to_RGB(0, 1, 255))

        self.assertEqual((0, 83, 255),
                         color_util.color_xy_brightness_to_RGB(0, 0, 255))

    def test_rgb_hex_to_rgb_list(self):
        """Test rgb_hex_to_rgb_list."""
        self.assertEqual([255, 255, 255],
                         color_util.rgb_hex_to_rgb_list('ffffff'))

        self.assertEqual([0, 0, 0],
                         color_util.rgb_hex_to_rgb_list('000000'))

        self.assertEqual([255, 255, 255, 255],
                         color_util.rgb_hex_to_rgb_list('ffffffff'))

        self.assertEqual([0, 0, 0, 0],
                         color_util.rgb_hex_to_rgb_list('00000000'))

        self.assertEqual([51, 153, 255],
                         color_util.rgb_hex_to_rgb_list('3399ff'))

        self.assertEqual([51, 153, 255, 0],
                         color_util.rgb_hex_to_rgb_list('3399ff00'))

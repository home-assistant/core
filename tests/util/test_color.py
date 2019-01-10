"""Test Home Assistant color util methods."""
import unittest
import homeassistant.util.color as color_util

import pytest
import voluptuous as vol


class TestColorUtil(unittest.TestCase):
    """Test color util methods."""

    # pylint: disable=invalid-name
    def test_color_RGB_to_xy_brightness(self):
        """Test color_RGB_to_xy_brightness."""
        assert (0, 0, 0) == \
            color_util.color_RGB_to_xy_brightness(0, 0, 0)
        assert (0.323, 0.329, 255) == \
            color_util.color_RGB_to_xy_brightness(255, 255, 255)

        assert (0.136, 0.04, 12) == \
            color_util.color_RGB_to_xy_brightness(0, 0, 255)

        assert (0.172, 0.747, 170) == \
            color_util.color_RGB_to_xy_brightness(0, 255, 0)

        assert (0.701, 0.299, 72) == \
            color_util.color_RGB_to_xy_brightness(255, 0, 0)

        assert (0.701, 0.299, 16) == \
            color_util.color_RGB_to_xy_brightness(128, 0, 0)

    def test_color_RGB_to_xy(self):
        """Test color_RGB_to_xy."""
        assert (0, 0) == \
            color_util.color_RGB_to_xy(0, 0, 0)
        assert (0.323, 0.329) == \
            color_util.color_RGB_to_xy(255, 255, 255)

        assert (0.136, 0.04) == \
            color_util.color_RGB_to_xy(0, 0, 255)

        assert (0.172, 0.747) == \
            color_util.color_RGB_to_xy(0, 255, 0)

        assert (0.701, 0.299) == \
            color_util.color_RGB_to_xy(255, 0, 0)

        assert (0.701, 0.299) == \
            color_util.color_RGB_to_xy(128, 0, 0)

    def test_color_xy_brightness_to_RGB(self):
        """Test color_xy_brightness_to_RGB."""
        assert (0, 0, 0) == \
            color_util.color_xy_brightness_to_RGB(1, 1, 0)

        assert (194, 186, 169) == \
            color_util.color_xy_brightness_to_RGB(.35, .35, 128)

        assert (255, 243, 222) == \
            color_util.color_xy_brightness_to_RGB(.35, .35, 255)

        assert (255, 0, 60) == \
            color_util.color_xy_brightness_to_RGB(1, 0, 255)

        assert (0, 255, 0) == \
            color_util.color_xy_brightness_to_RGB(0, 1, 255)

        assert (0, 63, 255) == \
            color_util.color_xy_brightness_to_RGB(0, 0, 255)

    def test_color_xy_to_RGB(self):
        """Test color_xy_to_RGB."""
        assert (255, 243, 222) == \
            color_util.color_xy_to_RGB(.35, .35)

        assert (255, 0, 60) == \
            color_util.color_xy_to_RGB(1, 0)

        assert (0, 255, 0) == \
            color_util.color_xy_to_RGB(0, 1)

        assert (0, 63, 255) == \
            color_util.color_xy_to_RGB(0, 0)

    def test_color_RGB_to_hsv(self):
        """Test color_RGB_to_hsv."""
        assert (0, 0, 0) == \
            color_util.color_RGB_to_hsv(0, 0, 0)

        assert (0, 0, 100) == \
            color_util.color_RGB_to_hsv(255, 255, 255)

        assert (240, 100, 100) == \
            color_util.color_RGB_to_hsv(0, 0, 255)

        assert (120, 100, 100) == \
            color_util.color_RGB_to_hsv(0, 255, 0)

        assert (0, 100, 100) == \
            color_util.color_RGB_to_hsv(255, 0, 0)

    def test_color_hsv_to_RGB(self):
        """Test color_hsv_to_RGB."""
        assert (0, 0, 0) == \
            color_util.color_hsv_to_RGB(0, 0, 0)

        assert (255, 255, 255) == \
            color_util.color_hsv_to_RGB(0, 0, 100)

        assert (0, 0, 255) == \
            color_util.color_hsv_to_RGB(240, 100, 100)

        assert (0, 255, 0) == \
            color_util.color_hsv_to_RGB(120, 100, 100)

        assert (255, 0, 0) == \
            color_util.color_hsv_to_RGB(0, 100, 100)

    def test_color_hsb_to_RGB(self):
        """Test color_hsb_to_RGB."""
        assert (0, 0, 0) == \
            color_util.color_hsb_to_RGB(0, 0, 0)

        assert (255, 255, 255) == \
            color_util.color_hsb_to_RGB(0, 0, 1.0)

        assert (0, 0, 255) == \
            color_util.color_hsb_to_RGB(240, 1.0, 1.0)

        assert (0, 255, 0) == \
            color_util.color_hsb_to_RGB(120, 1.0, 1.0)

        assert (255, 0, 0) == \
            color_util.color_hsb_to_RGB(0, 1.0, 1.0)

    def test_color_xy_to_hs(self):
        """Test color_xy_to_hs."""
        assert (47.294, 100) == \
            color_util.color_xy_to_hs(1, 1)

        assert (38.182, 12.941) == \
            color_util.color_xy_to_hs(.35, .35)

        assert (345.882, 100) == \
            color_util.color_xy_to_hs(1, 0)

        assert (120, 100) == \
            color_util.color_xy_to_hs(0, 1)

        assert (225.176, 100) == \
            color_util.color_xy_to_hs(0, 0)

    def test_color_hs_to_xy(self):
        """Test color_hs_to_xy."""
        assert (0.151, 0.343) == \
            color_util.color_hs_to_xy(180, 100)

        assert (0.356, 0.321) == \
            color_util.color_hs_to_xy(350, 12.5)

        assert (0.229, 0.474) == \
            color_util.color_hs_to_xy(140, 50)

        assert (0.474, 0.317) == \
            color_util.color_hs_to_xy(0, 40)

        assert (0.323, 0.329) == \
            color_util.color_hs_to_xy(360, 0)

    def test_rgb_hex_to_rgb_list(self):
        """Test rgb_hex_to_rgb_list."""
        assert [255, 255, 255] == \
            color_util.rgb_hex_to_rgb_list('ffffff')

        assert [0, 0, 0] == \
            color_util.rgb_hex_to_rgb_list('000000')

        assert [255, 255, 255, 255] == \
            color_util.rgb_hex_to_rgb_list('ffffffff')

        assert [0, 0, 0, 0] == \
            color_util.rgb_hex_to_rgb_list('00000000')

        assert [51, 153, 255] == \
            color_util.rgb_hex_to_rgb_list('3399ff')

        assert [51, 153, 255, 0] == \
            color_util.rgb_hex_to_rgb_list('3399ff00')

    def test_color_name_to_rgb_valid_name(self):
        """Test color_name_to_rgb."""
        assert (255, 0, 0) == \
            color_util.color_name_to_rgb('red')

        assert (0, 0, 255) == \
            color_util.color_name_to_rgb('blue')

        assert (0, 128, 0) == \
            color_util.color_name_to_rgb('green')

        # spaces in the name
        assert (72, 61, 139) == \
            color_util.color_name_to_rgb('dark slate blue')

        # spaces removed from name
        assert (72, 61, 139) == \
            color_util.color_name_to_rgb('darkslateblue')
        assert (72, 61, 139) == \
            color_util.color_name_to_rgb('dark slateblue')
        assert (72, 61, 139) == \
            color_util.color_name_to_rgb('darkslate blue')

    def test_color_name_to_rgb_unknown_name_raises_value_error(self):
        """Test color_name_to_rgb."""
        with pytest.raises(ValueError):
            color_util.color_name_to_rgb('not a color')

    def test_color_rgb_to_rgbw(self):
        """Test color_rgb_to_rgbw."""
        assert (0, 0, 0, 0) == \
            color_util.color_rgb_to_rgbw(0, 0, 0)

        assert (0, 0, 0, 255) == \
            color_util.color_rgb_to_rgbw(255, 255, 255)

        assert (255, 0, 0, 0) == \
            color_util.color_rgb_to_rgbw(255, 0, 0)

        assert (0, 255, 0, 0) == \
            color_util.color_rgb_to_rgbw(0, 255, 0)

        assert (0, 0, 255, 0) == \
            color_util.color_rgb_to_rgbw(0, 0, 255)

        assert (255, 127, 0, 0) == \
            color_util.color_rgb_to_rgbw(255, 127, 0)

        assert (255, 0, 0, 253) == \
            color_util.color_rgb_to_rgbw(255, 127, 127)

        assert (0, 0, 0, 127) == \
            color_util.color_rgb_to_rgbw(127, 127, 127)

    def test_color_rgbw_to_rgb(self):
        """Test color_rgbw_to_rgb."""
        assert (0, 0, 0) == \
            color_util.color_rgbw_to_rgb(0, 0, 0, 0)

        assert (255, 255, 255) == \
            color_util.color_rgbw_to_rgb(0, 0, 0, 255)

        assert (255, 0, 0) == \
            color_util.color_rgbw_to_rgb(255, 0, 0, 0)

        assert (0, 255, 0) == \
            color_util.color_rgbw_to_rgb(0, 255, 0, 0)

        assert (0, 0, 255) == \
            color_util.color_rgbw_to_rgb(0, 0, 255, 0)

        assert (255, 127, 0) == \
            color_util.color_rgbw_to_rgb(255, 127, 0, 0)

        assert (255, 127, 127) == \
            color_util.color_rgbw_to_rgb(255, 0, 0, 253)

        assert (127, 127, 127) == \
            color_util.color_rgbw_to_rgb(0, 0, 0, 127)

    def test_color_rgb_to_hex(self):
        """Test color_rgb_to_hex."""
        assert color_util.color_rgb_to_hex(255, 255, 255) == 'ffffff'
        assert color_util.color_rgb_to_hex(0, 0, 0) == '000000'
        assert color_util.color_rgb_to_hex(51, 153, 255) == '3399ff'
        assert color_util.color_rgb_to_hex(255, 67.9204190, 0) == 'ff4400'


class ColorTemperatureMiredToKelvinTests(unittest.TestCase):
    """Test color_temperature_mired_to_kelvin."""

    def test_should_return_25000_kelvin_when_input_is_40_mired(self):
        """Function should return 25000K if given 40 mired."""
        kelvin = color_util.color_temperature_mired_to_kelvin(40)
        assert 25000 == kelvin

    def test_should_return_5000_kelvin_when_input_is_200_mired(self):
        """Function should return 5000K if given 200 mired."""
        kelvin = color_util.color_temperature_mired_to_kelvin(200)
        assert 5000 == kelvin


class ColorTemperatureKelvinToMiredTests(unittest.TestCase):
    """Test color_temperature_kelvin_to_mired."""

    def test_should_return_40_mired_when_input_is_25000_kelvin(self):
        """Function should return 40 mired when given 25000 Kelvin."""
        mired = color_util.color_temperature_kelvin_to_mired(25000)
        assert 40 == mired

    def test_should_return_200_mired_when_input_is_5000_kelvin(self):
        """Function should return 200 mired when given 5000 Kelvin."""
        mired = color_util.color_temperature_kelvin_to_mired(5000)
        assert 200 == mired


class ColorTemperatureToRGB(unittest.TestCase):
    """Test color_temperature_to_rgb."""

    def test_returns_same_value_for_any_two_temperatures_below_1000(self):
        """Function should return same value for 999 Kelvin and 0 Kelvin."""
        rgb_1 = color_util.color_temperature_to_rgb(999)
        rgb_2 = color_util.color_temperature_to_rgb(0)
        assert rgb_1 == rgb_2

    def test_returns_same_value_for_any_two_temperatures_above_40000(self):
        """Function should return same value for 40001K and 999999K."""
        rgb_1 = color_util.color_temperature_to_rgb(40001)
        rgb_2 = color_util.color_temperature_to_rgb(999999)
        assert rgb_1 == rgb_2

    def test_should_return_pure_white_at_6600(self):
        """
        Function should return red=255, blue=255, green=255 when given 6600K.

        6600K is considered "pure white" light.
        This is just a rough estimate because the formula itself is a "best
        guess" approach.
        """
        rgb = color_util.color_temperature_to_rgb(6600)
        assert (255, 255, 255) == rgb

    def test_color_above_6600_should_have_more_blue_than_red_or_green(self):
        """Function should return a higher blue value for blue-ish light."""
        rgb = color_util.color_temperature_to_rgb(6700)
        assert rgb[2] > rgb[1]
        assert rgb[2] > rgb[0]

    def test_color_below_6600_should_have_more_red_than_blue_or_green(self):
        """Function should return a higher red value for red-ish light."""
        rgb = color_util.color_temperature_to_rgb(6500)
        assert rgb[0] > rgb[1]
        assert rgb[0] > rgb[2]


def test_get_color_in_voluptuous():
    """Test using the get method in color validation."""
    schema = vol.Schema(color_util.color_name_to_rgb)

    with pytest.raises(vol.Invalid):
        schema('not a color')

    assert schema('red') == (255, 0, 0)

"""Test Home Assistant color util methods."""
import unittest
import homeassistant.util.color as color_util


class TestColorUtil(unittest.TestCase):
    """Test color util methods."""

    # pylint: disable=invalid-name
    def test_color_RGB_to_xy(self):
        """Test color_RGB_to_xy."""
        self.assertEqual((0, 0, 0), color_util.color_RGB_to_xy(0, 0, 0))
        self.assertEqual((0.32, 0.336, 255),
                         color_util.color_RGB_to_xy(255, 255, 255))

        self.assertEqual((0.136, 0.04, 12),
                         color_util.color_RGB_to_xy(0, 0, 255))

        self.assertEqual((0.172, 0.747, 170),
                         color_util.color_RGB_to_xy(0, 255, 0))

        self.assertEqual((0.679, 0.321, 80),
                         color_util.color_RGB_to_xy(255, 0, 0))

    def test_color_xy_brightness_to_RGB(self):
        """Test color_RGB_to_xy."""
        self.assertEqual((0, 0, 0),
                         color_util.color_xy_brightness_to_RGB(1, 1, 0))

        self.assertEqual((255, 243, 222),
                         color_util.color_xy_brightness_to_RGB(.35, .35, 255))

        self.assertEqual((255, 0, 60),
                         color_util.color_xy_brightness_to_RGB(1, 0, 255))

        self.assertEqual((0, 255, 0),
                         color_util.color_xy_brightness_to_RGB(0, 1, 255))

        self.assertEqual((0, 63, 255),
                         color_util.color_xy_brightness_to_RGB(0, 0, 255))

    def test_color_RGB_to_hsv(self):
        """Test color_RGB_to_hsv."""
        self.assertEqual((0, 0, 0),
                         color_util.color_RGB_to_hsv(0, 0, 0))

        self.assertEqual((0, 0, 255),
                         color_util.color_RGB_to_hsv(255, 255, 255))

        self.assertEqual((43690, 255, 255),
                         color_util.color_RGB_to_hsv(0, 0, 255))

        self.assertEqual((21845, 255, 255),
                         color_util.color_RGB_to_hsv(0, 255, 0))

        self.assertEqual((0, 255, 255),
                         color_util.color_RGB_to_hsv(255, 0, 0))

    def test_color_hsv_to_RGB(self):
        """Test color_hsv_to_RGB."""
        self.assertEqual((0, 0, 0),
                         color_util.color_hsv_to_RGB(0, 0, 0))

        self.assertEqual((255, 255, 255),
                         color_util.color_hsv_to_RGB(0, 0, 255))

        self.assertEqual((0, 0, 255),
                         color_util.color_hsv_to_RGB(43690, 255, 255))

        self.assertEqual((0, 255, 0),
                         color_util.color_hsv_to_RGB(21845, 255, 255))

        self.assertEqual((255, 0, 0),
                         color_util.color_hsv_to_RGB(0, 255, 255))

    def test_color_hsb_to_RGB(self):
        """Test color_hsb_to_RGB."""
        self.assertEqual((0, 0, 0),
                         color_util.color_hsb_to_RGB(0, 0, 0))

        self.assertEqual((255, 255, 255),
                         color_util.color_hsb_to_RGB(0, 0, 1.0))

        self.assertEqual((0, 0, 255),
                         color_util.color_hsb_to_RGB(240, 1.0, 1.0))

        self.assertEqual((0, 255, 0),
                         color_util.color_hsb_to_RGB(120, 1.0, 1.0))

        self.assertEqual((255, 0, 0),
                         color_util.color_hsb_to_RGB(0, 1.0, 1.0))

    def test_color_xy_to_hs(self):
        """Test color_xy_to_hs."""
        self.assertEqual((8609, 255),
                         color_util.color_xy_to_hs(1, 1))

        self.assertEqual((6950, 32),
                         color_util.color_xy_to_hs(.35, .35))

        self.assertEqual((62965, 255),
                         color_util.color_xy_to_hs(1, 0))

        self.assertEqual((21845, 255),
                         color_util.color_xy_to_hs(0, 1))

        self.assertEqual((40992, 255),
                         color_util.color_xy_to_hs(0, 0))

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

    def test_color_name_to_rgb_valid_name(self):
        """Test color_name_to_rgb."""
        self.assertEqual((255, 0, 0),
                         color_util.color_name_to_rgb('red'))

        self.assertEqual((0, 0, 255),
                         color_util.color_name_to_rgb('blue'))

        self.assertEqual((0, 128, 0),
                         color_util.color_name_to_rgb('green'))

        # spaces in the name
        self.assertEqual((72, 61, 139),
                         color_util.color_name_to_rgb('dark slate blue'))

        # spaces removed from name
        self.assertEqual((72, 61, 139),
                         color_util.color_name_to_rgb('darkslateblue'))
        self.assertEqual((72, 61, 139),
                         color_util.color_name_to_rgb('dark slateblue'))
        self.assertEqual((72, 61, 139),
                         color_util.color_name_to_rgb('darkslate blue'))

    def test_color_name_to_rgb_unknown_name_default_white(self):
        """Test color_name_to_rgb."""
        self.assertEqual((255, 255, 255),
                         color_util.color_name_to_rgb('not a color'))

    def test_color_rgb_to_rgbw(self):
        """Test color_rgb_to_rgbw."""
        self.assertEqual((0, 0, 0, 0),
                         color_util.color_rgb_to_rgbw(0, 0, 0))

        self.assertEqual((0, 0, 0, 255),
                         color_util.color_rgb_to_rgbw(255, 255, 255))

        self.assertEqual((255, 0, 0, 0),
                         color_util.color_rgb_to_rgbw(255, 0, 0))

        self.assertEqual((0, 255, 0, 0),
                         color_util.color_rgb_to_rgbw(0, 255, 0))

        self.assertEqual((0, 0, 255, 0),
                         color_util.color_rgb_to_rgbw(0, 0, 255))

        self.assertEqual((255, 127, 0, 0),
                         color_util.color_rgb_to_rgbw(255, 127, 0))

        self.assertEqual((255, 0, 0, 253),
                         color_util.color_rgb_to_rgbw(255, 127, 127))

        self.assertEqual((0, 0, 0, 127),
                         color_util.color_rgb_to_rgbw(127, 127, 127))

    def test_color_rgbw_to_rgb(self):
        """Test color_rgbw_to_rgb."""
        self.assertEqual((0, 0, 0),
                         color_util.color_rgbw_to_rgb(0, 0, 0, 0))

        self.assertEqual((255, 255, 255),
                         color_util.color_rgbw_to_rgb(0, 0, 0, 255))

        self.assertEqual((255, 0, 0),
                         color_util.color_rgbw_to_rgb(255, 0, 0, 0))

        self.assertEqual((0, 255, 0),
                         color_util.color_rgbw_to_rgb(0, 255, 0, 0))

        self.assertEqual((0, 0, 255),
                         color_util.color_rgbw_to_rgb(0, 0, 255, 0))

        self.assertEqual((255, 127, 0),
                         color_util.color_rgbw_to_rgb(255, 127, 0, 0))

        self.assertEqual((255, 127, 127),
                         color_util.color_rgbw_to_rgb(255, 0, 0, 253))

        self.assertEqual((127, 127, 127),
                         color_util.color_rgbw_to_rgb(0, 0, 0, 127))

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
        self.assertEqual(25000, kelvin)

    def test_should_return_5000_kelvin_when_input_is_200_mired(self):
        """Function should return 5000K if given 200 mired."""
        kelvin = color_util.color_temperature_mired_to_kelvin(200)
        self.assertEqual(5000, kelvin)


class ColorTemperatureKelvinToMiredTests(unittest.TestCase):
    """Test color_temperature_kelvin_to_mired."""

    def test_should_return_40_mired_when_input_is_25000_kelvin(self):
        """Function should return 40 mired when given 25000 Kelvin."""
        mired = color_util.color_temperature_kelvin_to_mired(25000)
        self.assertEqual(40, mired)

    def test_should_return_200_mired_when_input_is_5000_kelvin(self):
        """Function should return 200 mired when given 5000 Kelvin."""
        mired = color_util.color_temperature_kelvin_to_mired(5000)
        self.assertEqual(200, mired)


class ColorTemperatureToRGB(unittest.TestCase):
    """Test color_temperature_to_rgb."""

    def test_returns_same_value_for_any_two_temperatures_below_1000(self):
        """Function should return same value for 999 Kelvin and 0 Kelvin."""
        rgb_1 = color_util.color_temperature_to_rgb(999)
        rgb_2 = color_util.color_temperature_to_rgb(0)
        self.assertEqual(rgb_1, rgb_2)

    def test_returns_same_value_for_any_two_temperatures_above_40000(self):
        """Function should return same value for 40001K and 999999K."""
        rgb_1 = color_util.color_temperature_to_rgb(40001)
        rgb_2 = color_util.color_temperature_to_rgb(999999)
        self.assertEqual(rgb_1, rgb_2)

    def test_should_return_pure_white_at_6600(self):
        """
        Function should return red=255, blue=255, green=255 when given 6600K.

        6600K is considered "pure white" light.
        This is just a rough estimate because the formula itself is a "best
        guess" approach.
        """
        rgb = color_util.color_temperature_to_rgb(6600)
        self.assertEqual((255, 255, 255), rgb)

    def test_color_above_6600_should_have_more_blue_than_red_or_green(self):
        """Function should return a higher blue value for blue-ish light."""
        rgb = color_util.color_temperature_to_rgb(6700)
        self.assertGreater(rgb[2], rgb[1])
        self.assertGreater(rgb[2], rgb[0])

    def test_color_below_6600_should_have_more_red_than_blue_or_green(self):
        """Function should return a higher red value for red-ish light."""
        rgb = color_util.color_temperature_to_rgb(6500)
        self.assertGreater(rgb[0], rgb[1])
        self.assertGreater(rgb[0], rgb[2])

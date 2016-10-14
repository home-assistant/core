"""Color util methods."""
import logging
import math

from typing import Tuple

_LOGGER = logging.getLogger(__name__)

HASS_COLOR_MAX = 500  # mireds (inverted)
HASS_COLOR_MIN = 154
COLORS = {
    'white': (255, 255, 255), 'beige': (245, 245, 220),
    'tan': (210, 180, 140), 'gray': (128, 128, 128),
    'navy blue': (0, 0, 128), 'royal blue': (8, 76, 158),
    'blue': (0, 0, 255), 'azure': (0, 127, 255), 'aqua': (127, 255, 212),
    'teal': (0, 128, 128), 'green': (0, 255, 0),
    'forest green': (34, 139, 34), 'olive': (128, 128, 0),
    'chartreuse': (127, 255, 0), 'lime': (191, 255, 0),
    'golden': (255, 215, 0), 'red': (255, 0, 0), 'coral': (0, 63, 72),
    'hot pink': (252, 15, 192), 'fuchsia': (255, 119, 255),
    'lavender': (181, 126, 220), 'indigo': (75, 0, 130),
    'maroon': (128, 0, 0), 'crimson': (220, 20, 60)}


def color_name_to_rgb(color_name):
    """Convert color name to RGB hex value."""
    hex_value = COLORS.get(color_name.lower())

    if not hex_value:
        _LOGGER.error('unknown color supplied %s default to white', color_name)
        hex_value = COLORS['white']

    return hex_value


# Taken from:
# http://www.developers.meethue.com/documentation/color-conversions-rgb-xy
# License: Code is given as is. Use at your own risk and discretion.
# pylint: disable=invalid-name
def color_RGB_to_xy(iR: int, iG: int, iB: int) -> Tuple[float, float, int]:
    """Convert from RGB color to XY color."""
    if iR + iG + iB == 0:
        return 0.0, 0.0, 0

    R = iR / 255
    B = iB / 255
    G = iG / 255

    # Gamma correction
    R = pow((R + 0.055) / (1.0 + 0.055),
            2.4) if (R > 0.04045) else (R / 12.92)
    G = pow((G + 0.055) / (1.0 + 0.055),
            2.4) if (G > 0.04045) else (G / 12.92)
    B = pow((B + 0.055) / (1.0 + 0.055),
            2.4) if (B > 0.04045) else (B / 12.92)

    # Wide RGB D65 conversion formula
    X = R * 0.664511 + G * 0.154324 + B * 0.162028
    Y = R * 0.313881 + G * 0.668433 + B * 0.047685
    Z = R * 0.000088 + G * 0.072310 + B * 0.986039

    # Convert XYZ to xy
    x = X / (X + Y + Z)
    y = Y / (X + Y + Z)

    # Brightness
    Y = 1 if Y > 1 else Y
    brightness = round(Y * 255)

    return round(x, 3), round(y, 3), brightness


# taken from
# https://github.com/benknight/hue-python-rgb-converter/blob/master/rgb_cie.py
# Copyright (c) 2014 Benjamin Knight / MIT License.
def color_xy_brightness_to_RGB(vX: float, vY: float,
                               ibrightness: int) -> Tuple[int, int, int]:
    """Convert from XYZ to RGB."""
    brightness = ibrightness / 255.
    if brightness == 0:
        return (0, 0, 0)

    Y = brightness

    if vY == 0:
        vY += 0.00000000001

    X = (Y / vY) * vX
    Z = (Y / vY) * (1 - vX - vY)

    # Convert to RGB using Wide RGB D65 conversion.
    r = X * 1.612 - Y * 0.203 - Z * 0.302
    g = -X * 0.509 + Y * 1.412 + Z * 0.066
    b = X * 0.026 - Y * 0.072 + Z * 0.962

    # Apply reverse gamma correction.
    r, g, b = map(
        lambda x: (12.92 * x) if (x <= 0.0031308) else
        ((1.0 + 0.055) * pow(x, (1.0 / 2.4)) - 0.055),
        [r, g, b]
    )

    # Bring all negative components to zero.
    r, g, b = map(lambda x: max(0, x), [r, g, b])

    # If one component is greater than 1, weight components by that value.
    max_component = max(r, g, b)
    if max_component > 1:
        r, g, b = map(lambda x: x / max_component, [r, g, b])

    ir, ig, ib = map(lambda x: int(x * 255), [r, g, b])

    return (ir, ig, ib)


def _match_max_scale(input_colors: Tuple[int, ...],
                     output_colors: Tuple[int, ...]) -> Tuple[int, ...]:
    """Match the maximum value of the output to the input."""
    max_in = max(input_colors)
    max_out = max(output_colors)
    if max_out == 0:
        factor = 0.0
    else:
        factor = max_in / max_out
    return tuple(int(round(i * factor)) for i in output_colors)


def color_rgb_to_rgbw(r, g, b):
    """Convert an rgb color to an rgbw representation."""
    # Calculate the white channel as the minimum of input rgb channels.
    # Subtract the white portion from the remaining rgb channels.
    w = min(r, g, b)
    rgbw = (r - w, g - w, b - w, w)

    # Match the output maximum value to the input. This ensures the full
    # channel range is used.
    return _match_max_scale((r, g, b), rgbw)


def color_rgbw_to_rgb(r, g, b, w):
    """Convert an rgbw color to an rgb representation."""
    # Add the white channel back into the rgb channels.
    rgb = (r + w, g + w, b + w)

    # Match the output maximum value to the input. This ensures the the
    # output doesn't overflow.
    return _match_max_scale((r, g, b, w), rgb)


def rgb_hex_to_rgb_list(hex_string):
    """Return an RGB color value list from a hex color string."""
    return [int(hex_string[i:i + len(hex_string) // 3], 16)
            for i in range(0,
                           len(hex_string),
                           len(hex_string) // 3)]


def color_temperature_to_rgb(color_temperature_kelvin):
    """
    Return an RGB color from a color temperature in Kelvin.

    This is a rough approximation based on the formula provided by T. Helland
    http://www.tannerhelland.com/4435/convert-temperature-rgb-algorithm-code/
    """
    # range check
    if color_temperature_kelvin < 1000:
        color_temperature_kelvin = 1000
    elif color_temperature_kelvin > 40000:
        color_temperature_kelvin = 40000

    tmp_internal = color_temperature_kelvin / 100.0

    red = _get_red(tmp_internal)

    green = _get_green(tmp_internal)

    blue = _get_blue(tmp_internal)

    return (red, green, blue)


def _bound(color_component: float, minimum: float=0,
           maximum: float=255) -> float:
    """
    Bound the given color component value between the given min and max values.

    The minimum and maximum values will be included in the valid output.
    i.e. Given a color_component of 0 and a minimum of 10, the returned value
    will be 10.
    """
    color_component_out = max(color_component, minimum)
    return min(color_component_out, maximum)


def _get_red(temperature: float) -> float:
    """Get the red component of the temperature in RGB space."""
    if temperature <= 66:
        return 255
    tmp_red = 329.698727446 * math.pow(temperature - 60, -0.1332047592)
    return _bound(tmp_red)


def _get_green(temperature: float) -> float:
    """Get the green component of the given color temp in RGB space."""
    if temperature <= 66:
        green = 99.4708025861 * math.log(temperature) - 161.1195681661
    else:
        green = 288.1221695283 * math.pow(temperature - 60, -0.0755148492)
    return _bound(green)


def _get_blue(temperature: float) -> float:
    """Get the blue component of the given color temperature in RGB space."""
    if temperature >= 66:
        return 255
    if temperature <= 19:
        return 0
    blue = 138.5177312231 * math.log(temperature - 10) - 305.0447927307
    return _bound(blue)


def color_temperature_mired_to_kelvin(mired_temperature):
    """Convert absolute mired shift to degrees kelvin."""
    return 1000000 / mired_temperature


def color_temperature_kelvin_to_mired(kelvin_temperature):
    """Convert degrees kelvin to mired shift."""
    return 1000000 / kelvin_temperature

"""Color util methods."""
from __future__ import annotations

import colorsys
import math
from typing import NamedTuple

import attr


class RGBColor(NamedTuple):
    """RGB hex values."""

    r: int
    g: int
    b: int


# Official CSS3 colors from w3.org:
# https://www.w3.org/TR/2010/PR-css3-color-20101028/#html4
# names do not have spaces in them so that we can compare against
# requests more easily (by removing spaces from the requests as well).
# This lets "dark seagreen" and "dark sea green" both match the same
# color "darkseagreen".
COLORS = {
    "aliceblue": RGBColor(240, 248, 255),
    "antiquewhite": RGBColor(250, 235, 215),
    "aqua": RGBColor(0, 255, 255),
    "aquamarine": RGBColor(127, 255, 212),
    "azure": RGBColor(240, 255, 255),
    "beige": RGBColor(245, 245, 220),
    "bisque": RGBColor(255, 228, 196),
    "black": RGBColor(0, 0, 0),
    "blanchedalmond": RGBColor(255, 235, 205),
    "blue": RGBColor(0, 0, 255),
    "blueviolet": RGBColor(138, 43, 226),
    "brown": RGBColor(165, 42, 42),
    "burlywood": RGBColor(222, 184, 135),
    "cadetblue": RGBColor(95, 158, 160),
    "chartreuse": RGBColor(127, 255, 0),
    "chocolate": RGBColor(210, 105, 30),
    "coral": RGBColor(255, 127, 80),
    "cornflowerblue": RGBColor(100, 149, 237),
    "cornsilk": RGBColor(255, 248, 220),
    "crimson": RGBColor(220, 20, 60),
    "cyan": RGBColor(0, 255, 255),
    "darkblue": RGBColor(0, 0, 139),
    "darkcyan": RGBColor(0, 139, 139),
    "darkgoldenrod": RGBColor(184, 134, 11),
    "darkgray": RGBColor(169, 169, 169),
    "darkgreen": RGBColor(0, 100, 0),
    "darkgrey": RGBColor(169, 169, 169),
    "darkkhaki": RGBColor(189, 183, 107),
    "darkmagenta": RGBColor(139, 0, 139),
    "darkolivegreen": RGBColor(85, 107, 47),
    "darkorange": RGBColor(255, 140, 0),
    "darkorchid": RGBColor(153, 50, 204),
    "darkred": RGBColor(139, 0, 0),
    "darksalmon": RGBColor(233, 150, 122),
    "darkseagreen": RGBColor(143, 188, 143),
    "darkslateblue": RGBColor(72, 61, 139),
    "darkslategray": RGBColor(47, 79, 79),
    "darkslategrey": RGBColor(47, 79, 79),
    "darkturquoise": RGBColor(0, 206, 209),
    "darkviolet": RGBColor(148, 0, 211),
    "deeppink": RGBColor(255, 20, 147),
    "deepskyblue": RGBColor(0, 191, 255),
    "dimgray": RGBColor(105, 105, 105),
    "dimgrey": RGBColor(105, 105, 105),
    "dodgerblue": RGBColor(30, 144, 255),
    "firebrick": RGBColor(178, 34, 34),
    "floralwhite": RGBColor(255, 250, 240),
    "forestgreen": RGBColor(34, 139, 34),
    "fuchsia": RGBColor(255, 0, 255),
    "gainsboro": RGBColor(220, 220, 220),
    "ghostwhite": RGBColor(248, 248, 255),
    "gold": RGBColor(255, 215, 0),
    "goldenrod": RGBColor(218, 165, 32),
    "gray": RGBColor(128, 128, 128),
    "green": RGBColor(0, 128, 0),
    "greenyellow": RGBColor(173, 255, 47),
    "grey": RGBColor(128, 128, 128),
    "honeydew": RGBColor(240, 255, 240),
    "hotpink": RGBColor(255, 105, 180),
    "indianred": RGBColor(205, 92, 92),
    "indigo": RGBColor(75, 0, 130),
    "ivory": RGBColor(255, 255, 240),
    "khaki": RGBColor(240, 230, 140),
    "lavender": RGBColor(230, 230, 250),
    "lavenderblush": RGBColor(255, 240, 245),
    "lawngreen": RGBColor(124, 252, 0),
    "lemonchiffon": RGBColor(255, 250, 205),
    "lightblue": RGBColor(173, 216, 230),
    "lightcoral": RGBColor(240, 128, 128),
    "lightcyan": RGBColor(224, 255, 255),
    "lightgoldenrodyellow": RGBColor(250, 250, 210),
    "lightgray": RGBColor(211, 211, 211),
    "lightgreen": RGBColor(144, 238, 144),
    "lightgrey": RGBColor(211, 211, 211),
    "lightpink": RGBColor(255, 182, 193),
    "lightsalmon": RGBColor(255, 160, 122),
    "lightseagreen": RGBColor(32, 178, 170),
    "lightskyblue": RGBColor(135, 206, 250),
    "lightslategray": RGBColor(119, 136, 153),
    "lightslategrey": RGBColor(119, 136, 153),
    "lightsteelblue": RGBColor(176, 196, 222),
    "lightyellow": RGBColor(255, 255, 224),
    "lime": RGBColor(0, 255, 0),
    "limegreen": RGBColor(50, 205, 50),
    "linen": RGBColor(250, 240, 230),
    "magenta": RGBColor(255, 0, 255),
    "maroon": RGBColor(128, 0, 0),
    "mediumaquamarine": RGBColor(102, 205, 170),
    "mediumblue": RGBColor(0, 0, 205),
    "mediumorchid": RGBColor(186, 85, 211),
    "mediumpurple": RGBColor(147, 112, 219),
    "mediumseagreen": RGBColor(60, 179, 113),
    "mediumslateblue": RGBColor(123, 104, 238),
    "mediumspringgreen": RGBColor(0, 250, 154),
    "mediumturquoise": RGBColor(72, 209, 204),
    "mediumvioletred": RGBColor(199, 21, 133),
    "midnightblue": RGBColor(25, 25, 112),
    "mintcream": RGBColor(245, 255, 250),
    "mistyrose": RGBColor(255, 228, 225),
    "moccasin": RGBColor(255, 228, 181),
    "navajowhite": RGBColor(255, 222, 173),
    "navy": RGBColor(0, 0, 128),
    "navyblue": RGBColor(0, 0, 128),
    "oldlace": RGBColor(253, 245, 230),
    "olive": RGBColor(128, 128, 0),
    "olivedrab": RGBColor(107, 142, 35),
    "orange": RGBColor(255, 165, 0),
    "orangered": RGBColor(255, 69, 0),
    "orchid": RGBColor(218, 112, 214),
    "palegoldenrod": RGBColor(238, 232, 170),
    "palegreen": RGBColor(152, 251, 152),
    "paleturquoise": RGBColor(175, 238, 238),
    "palevioletred": RGBColor(219, 112, 147),
    "papayawhip": RGBColor(255, 239, 213),
    "peachpuff": RGBColor(255, 218, 185),
    "peru": RGBColor(205, 133, 63),
    "pink": RGBColor(255, 192, 203),
    "plum": RGBColor(221, 160, 221),
    "powderblue": RGBColor(176, 224, 230),
    "purple": RGBColor(128, 0, 128),
    "red": RGBColor(255, 0, 0),
    "rosybrown": RGBColor(188, 143, 143),
    "royalblue": RGBColor(65, 105, 225),
    "saddlebrown": RGBColor(139, 69, 19),
    "salmon": RGBColor(250, 128, 114),
    "sandybrown": RGBColor(244, 164, 96),
    "seagreen": RGBColor(46, 139, 87),
    "seashell": RGBColor(255, 245, 238),
    "sienna": RGBColor(160, 82, 45),
    "silver": RGBColor(192, 192, 192),
    "skyblue": RGBColor(135, 206, 235),
    "slateblue": RGBColor(106, 90, 205),
    "slategray": RGBColor(112, 128, 144),
    "slategrey": RGBColor(112, 128, 144),
    "snow": RGBColor(255, 250, 250),
    "springgreen": RGBColor(0, 255, 127),
    "steelblue": RGBColor(70, 130, 180),
    "tan": RGBColor(210, 180, 140),
    "teal": RGBColor(0, 128, 128),
    "thistle": RGBColor(216, 191, 216),
    "tomato": RGBColor(255, 99, 71),
    "turquoise": RGBColor(64, 224, 208),
    "violet": RGBColor(238, 130, 238),
    "wheat": RGBColor(245, 222, 179),
    "white": RGBColor(255, 255, 255),
    "whitesmoke": RGBColor(245, 245, 245),
    "yellow": RGBColor(255, 255, 0),
    "yellowgreen": RGBColor(154, 205, 50),
    # And...
    "homeassistant": RGBColor(3, 169, 244),
}


@attr.s()
class XYPoint:
    """Represents a CIE 1931 XY coordinate pair."""

    x: float = attr.ib()  # pylint: disable=invalid-name
    y: float = attr.ib()  # pylint: disable=invalid-name


@attr.s()
class GamutType:
    """Represents the Gamut of a light."""

    # ColorGamut = gamut(xypoint(xR,yR),xypoint(xG,yG),xypoint(xB,yB))
    red: XYPoint = attr.ib()
    green: XYPoint = attr.ib()
    blue: XYPoint = attr.ib()


def color_name_to_rgb(color_name: str) -> RGBColor:
    """Convert color name to RGB hex value."""
    # COLORS map has no spaces in it, so make the color_name have no
    # spaces in it as well for matching purposes
    hex_value = COLORS.get(color_name.replace(" ", "").lower())
    if not hex_value:
        raise ValueError("Unknown color")

    return hex_value


# pylint: disable=invalid-name


def color_RGB_to_xy(
    iR: int, iG: int, iB: int, Gamut: GamutType | None = None
) -> tuple[float, float]:
    """Convert from RGB color to XY color."""
    return color_RGB_to_xy_brightness(iR, iG, iB, Gamut)[:2]


# Taken from:
# https://github.com/PhilipsHue/PhilipsHueSDK-iOS-OSX/blob/00187a3/ApplicationDesignNotes/RGB%20to%20xy%20Color%20conversion.md
# License: Code is given as is. Use at your own risk and discretion.
def color_RGB_to_xy_brightness(
    iR: int, iG: int, iB: int, Gamut: GamutType | None = None
) -> tuple[float, float, int]:
    """Convert from RGB color to XY color."""
    if iR + iG + iB == 0:
        return 0.0, 0.0, 0

    R = iR / 255
    B = iB / 255
    G = iG / 255

    # Gamma correction
    R = pow((R + 0.055) / (1.0 + 0.055), 2.4) if (R > 0.04045) else (R / 12.92)
    G = pow((G + 0.055) / (1.0 + 0.055), 2.4) if (G > 0.04045) else (G / 12.92)
    B = pow((B + 0.055) / (1.0 + 0.055), 2.4) if (B > 0.04045) else (B / 12.92)

    # Wide RGB D65 conversion formula
    X = R * 0.664511 + G * 0.154324 + B * 0.162028
    Y = R * 0.283881 + G * 0.668433 + B * 0.047685
    Z = R * 0.000088 + G * 0.072310 + B * 0.986039

    # Convert XYZ to xy
    x = X / (X + Y + Z)
    y = Y / (X + Y + Z)

    # Brightness
    Y = 1 if Y > 1 else Y
    brightness = round(Y * 255)

    # Check if the given xy value is within the color-reach of the lamp.
    if Gamut:
        in_reach = check_point_in_lamps_reach((x, y), Gamut)
        if not in_reach:
            xy_closest = get_closest_point_to_point((x, y), Gamut)
            x = xy_closest[0]
            y = xy_closest[1]

    return round(x, 3), round(y, 3), brightness


def color_xy_to_RGB(
    vX: float, vY: float, Gamut: GamutType | None = None
) -> tuple[int, int, int]:
    """Convert from XY to a normalized RGB."""
    return color_xy_brightness_to_RGB(vX, vY, 255, Gamut)


# Converted to Python from Obj-C, original source from:
# https://github.com/PhilipsHue/PhilipsHueSDK-iOS-OSX/blob/00187a3/ApplicationDesignNotes/RGB%20to%20xy%20Color%20conversion.md
def color_xy_brightness_to_RGB(
    vX: float, vY: float, ibrightness: int, Gamut: GamutType | None = None
) -> tuple[int, int, int]:
    """Convert from XYZ to RGB."""
    if Gamut and not check_point_in_lamps_reach((vX, vY), Gamut):
        xy_closest = get_closest_point_to_point((vX, vY), Gamut)
        vX = xy_closest[0]
        vY = xy_closest[1]

    brightness = ibrightness / 255.0
    if brightness == 0.0:
        return (0, 0, 0)

    Y = brightness

    if vY == 0.0:
        vY += 0.00000000001

    X = (Y / vY) * vX
    Z = (Y / vY) * (1 - vX - vY)

    # Convert to RGB using Wide RGB D65 conversion.
    r = X * 1.656492 - Y * 0.354851 - Z * 0.255038
    g = -X * 0.707196 + Y * 1.655397 + Z * 0.036152
    b = X * 0.051713 - Y * 0.121364 + Z * 1.011530

    # Apply reverse gamma correction.
    r, g, b = (
        12.92 * x if (x <= 0.0031308) else ((1.0 + 0.055) * pow(x, (1.0 / 2.4)) - 0.055)
        for x in (r, g, b)
    )

    # Bring all negative components to zero.
    r, g, b = (max(0, x) for x in (r, g, b))

    # If one component is greater than 1, weight components by that value.
    max_component = max(r, g, b)
    if max_component > 1:
        r, g, b = (x / max_component for x in (r, g, b))

    ir, ig, ib = (int(x * 255) for x in (r, g, b))

    return (ir, ig, ib)


def color_hsb_to_RGB(fH: float, fS: float, fB: float) -> tuple[int, int, int]:
    """Convert a hsb into its rgb representation."""
    if fS == 0.0:
        fV = int(fB * 255)
        return fV, fV, fV

    r = g = b = 0
    h = fH / 60
    f = h - float(math.floor(h))
    p = fB * (1 - fS)
    q = fB * (1 - fS * f)
    t = fB * (1 - (fS * (1 - f)))

    if int(h) == 0:
        r = int(fB * 255)
        g = int(t * 255)
        b = int(p * 255)
    elif int(h) == 1:
        r = int(q * 255)
        g = int(fB * 255)
        b = int(p * 255)
    elif int(h) == 2:
        r = int(p * 255)
        g = int(fB * 255)
        b = int(t * 255)
    elif int(h) == 3:
        r = int(p * 255)
        g = int(q * 255)
        b = int(fB * 255)
    elif int(h) == 4:
        r = int(t * 255)
        g = int(p * 255)
        b = int(fB * 255)
    elif int(h) == 5:
        r = int(fB * 255)
        g = int(p * 255)
        b = int(q * 255)

    return (r, g, b)


def color_RGB_to_hsv(iR: float, iG: float, iB: float) -> tuple[float, float, float]:
    """Convert an rgb color to its hsv representation.

    Hue is scaled 0-360
    Sat is scaled 0-100
    Val is scaled 0-100
    """
    fHSV = colorsys.rgb_to_hsv(iR / 255.0, iG / 255.0, iB / 255.0)
    return round(fHSV[0] * 360, 3), round(fHSV[1] * 100, 3), round(fHSV[2] * 100, 3)


def color_RGB_to_hs(iR: float, iG: float, iB: float) -> tuple[float, float]:
    """Convert an rgb color to its hs representation."""
    return color_RGB_to_hsv(iR, iG, iB)[:2]


def color_hsv_to_RGB(iH: float, iS: float, iV: float) -> tuple[int, int, int]:
    """Convert an hsv color into its rgb representation.

    Hue is scaled 0-360
    Sat is scaled 0-100
    Val is scaled 0-100
    """
    fRGB = colorsys.hsv_to_rgb(iH / 360, iS / 100, iV / 100)
    return (int(fRGB[0] * 255), int(fRGB[1] * 255), int(fRGB[2] * 255))


def color_hs_to_RGB(iH: float, iS: float) -> tuple[int, int, int]:
    """Convert an hsv color into its rgb representation."""
    return color_hsv_to_RGB(iH, iS, 100)


def color_xy_to_hs(
    vX: float, vY: float, Gamut: GamutType | None = None
) -> tuple[float, float]:
    """Convert an xy color to its hs representation."""
    h, s, _ = color_RGB_to_hsv(*color_xy_to_RGB(vX, vY, Gamut))
    return h, s


def color_hs_to_xy(
    iH: float, iS: float, Gamut: GamutType | None = None
) -> tuple[float, float]:
    """Convert an hs color to its xy representation."""
    return color_RGB_to_xy(*color_hs_to_RGB(iH, iS), Gamut)


def match_max_scale(
    input_colors: tuple[int, ...], output_colors: tuple[float, ...]
) -> tuple[int, ...]:
    """Match the maximum value of the output to the input."""
    max_in = max(input_colors)
    max_out = max(output_colors)
    if max_out == 0:
        factor = 0.0
    else:
        factor = max_in / max_out
    return tuple(int(round(i * factor)) for i in output_colors)


def color_rgb_to_rgbw(r: int, g: int, b: int) -> tuple[int, int, int, int]:
    """Convert an rgb color to an rgbw representation."""
    # Calculate the white channel as the minimum of input rgb channels.
    # Subtract the white portion from the remaining rgb channels.
    w = min(r, g, b)
    rgbw = (r - w, g - w, b - w, w)

    # Match the output maximum value to the input. This ensures the full
    # channel range is used.
    return match_max_scale((r, g, b), rgbw)  # type: ignore[return-value]


def color_rgbw_to_rgb(r: int, g: int, b: int, w: int) -> tuple[int, int, int]:
    """Convert an rgbw color to an rgb representation."""
    # Add the white channel to the rgb channels.
    rgb = (r + w, g + w, b + w)

    # Match the output maximum value to the input. This ensures the
    # output doesn't overflow.
    return match_max_scale((r, g, b, w), rgb)  # type: ignore[return-value]


def color_rgb_to_rgbww(
    r: int, g: int, b: int, min_kelvin: int, max_kelvin: int
) -> tuple[int, int, int, int, int]:
    """Convert an rgb color to an rgbww representation."""
    # Find the color temperature when both white channels have equal brightness
    max_mireds = color_temperature_kelvin_to_mired(min_kelvin)
    min_mireds = color_temperature_kelvin_to_mired(max_kelvin)
    mired_range = max_mireds - min_mireds
    mired_midpoint = min_mireds + mired_range / 2
    color_temp_kelvin = color_temperature_mired_to_kelvin(mired_midpoint)
    w_r, w_g, w_b = color_temperature_to_rgb(color_temp_kelvin)

    # Find the ratio of the midpoint white in the input rgb channels
    white_level = min(
        r / w_r if w_r else 0, g / w_g if w_g else 0, b / w_b if w_b else 0
    )

    # Subtract the white portion from the rgb channels.
    rgb = (r - w_r * white_level, g - w_g * white_level, b - w_b * white_level)
    rgbww = (*rgb, round(white_level * 255), round(white_level * 255))

    # Match the output maximum value to the input. This ensures the full
    # channel range is used.
    return match_max_scale((r, g, b), rgbww)  # type: ignore[return-value]


def color_rgbww_to_rgb(
    r: int, g: int, b: int, cw: int, ww: int, min_kelvin: int, max_kelvin: int
) -> tuple[int, int, int]:
    """Convert an rgbww color to an rgb representation."""
    # Calculate color temperature of the white channels
    max_mireds = color_temperature_kelvin_to_mired(min_kelvin)
    min_mireds = color_temperature_kelvin_to_mired(max_kelvin)
    mired_range = max_mireds - min_mireds
    try:
        ct_ratio = ww / (cw + ww)
    except ZeroDivisionError:
        ct_ratio = 0.5
    color_temp_mired = min_mireds + ct_ratio * mired_range
    if color_temp_mired:
        color_temp_kelvin = color_temperature_mired_to_kelvin(color_temp_mired)
    else:
        color_temp_kelvin = 0
    w_r, w_g, w_b = color_temperature_to_rgb(color_temp_kelvin)
    white_level = max(cw, ww) / 255

    # Add the white channels to the rgb channels.
    rgb = (r + w_r * white_level, g + w_g * white_level, b + w_b * white_level)

    # Match the output maximum value to the input. This ensures the
    # output doesn't overflow.
    return match_max_scale((r, g, b, cw, ww), rgb)  # type: ignore[return-value]


def color_rgb_to_hex(r: int, g: int, b: int) -> str:
    """Return a RGB color from a hex color string."""
    return f"{round(r):02x}{round(g):02x}{round(b):02x}"


def rgb_hex_to_rgb_list(hex_string: str) -> list[int]:
    """Return an RGB color value list from a hex color string."""
    return [
        int(hex_string[i : i + len(hex_string) // 3], 16)
        for i in range(0, len(hex_string), len(hex_string) // 3)
    ]


def color_temperature_to_hs(color_temperature_kelvin: float) -> tuple[float, float]:
    """Return an hs color from a color temperature in Kelvin."""
    return color_RGB_to_hs(*color_temperature_to_rgb(color_temperature_kelvin))


def color_temperature_to_rgb(
    color_temperature_kelvin: float,
) -> tuple[float, float, float]:
    """Return an RGB color from a color temperature in Kelvin.

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

    return red, green, blue


def color_temperature_to_rgbww(
    temperature: int, brightness: int, min_kelvin: int, max_kelvin: int
) -> tuple[int, int, int, int, int]:
    """Convert color temperature in kelvin to rgbcw.

    Returns a (r, g, b, cw, ww) tuple.
    """
    max_mireds = color_temperature_kelvin_to_mired(min_kelvin)
    min_mireds = color_temperature_kelvin_to_mired(max_kelvin)
    temperature = color_temperature_kelvin_to_mired(temperature)
    mired_range = max_mireds - min_mireds
    cold = ((max_mireds - temperature) / mired_range) * brightness
    warm = brightness - cold
    return (0, 0, 0, round(cold), round(warm))


def rgbww_to_color_temperature(
    rgbww: tuple[int, int, int, int, int], min_kelvin: int, max_kelvin: int
) -> tuple[int, int]:
    """Convert rgbcw to color temperature in kelvin.

    Returns a tuple (color_temperature, brightness).
    """
    _, _, _, cold, warm = rgbww
    return _white_levels_to_color_temperature(cold, warm, min_kelvin, max_kelvin)


def _white_levels_to_color_temperature(
    cold: int, warm: int, min_kelvin: int, max_kelvin: int
) -> tuple[int, int]:
    """Convert whites to color temperature in kelvin.

    Returns a tuple (color_temperature, brightness).
    """
    max_mireds = color_temperature_kelvin_to_mired(min_kelvin)
    min_mireds = color_temperature_kelvin_to_mired(max_kelvin)
    brightness = warm / 255 + cold / 255
    if brightness == 0:
        # Return the warmest color if brightness is 0
        return (min_kelvin, 0)
    return round(
        color_temperature_mired_to_kelvin(
            ((cold / 255 / brightness) * (min_mireds - max_mireds)) + max_mireds
        )
    ), min(255, round(brightness * 255))


def _clamp(color_component: float, minimum: float = 0, maximum: float = 255) -> float:
    """Clamp the given color component value between the given min and max values.

    The range defined by the minimum and maximum values is inclusive, i.e. given a
    color_component of 0 and a minimum of 10, the returned value is 10.
    """
    color_component_out = max(color_component, minimum)
    return min(color_component_out, maximum)


def _get_red(temperature: float) -> float:
    """Get the red component of the temperature in RGB space."""
    if temperature <= 66:
        return 255
    tmp_red = 329.698727446 * math.pow(temperature - 60, -0.1332047592)
    return _clamp(tmp_red)


def _get_green(temperature: float) -> float:
    """Get the green component of the given color temp in RGB space."""
    if temperature <= 66:
        green = 99.4708025861 * math.log(temperature) - 161.1195681661
    else:
        green = 288.1221695283 * math.pow(temperature - 60, -0.0755148492)
    return _clamp(green)


def _get_blue(temperature: float) -> float:
    """Get the blue component of the given color temperature in RGB space."""
    if temperature >= 66:
        return 255
    if temperature <= 19:
        return 0
    blue = 138.5177312231 * math.log(temperature - 10) - 305.0447927307
    return _clamp(blue)


def color_temperature_mired_to_kelvin(mired_temperature: float) -> int:
    """Convert absolute mired shift to degrees kelvin."""
    return math.floor(1000000 / mired_temperature)


def color_temperature_kelvin_to_mired(kelvin_temperature: float) -> int:
    """Convert degrees kelvin to mired shift."""
    return math.floor(1000000 / kelvin_temperature)


# The following 5 functions are adapted from rgbxy provided by Benjamin Knight
# License: The MIT License (MIT), 2014.
# https://github.com/benknight/hue-python-rgb-converter
def cross_product(p1: XYPoint, p2: XYPoint) -> float:
    """Calculate the cross product of two XYPoints."""
    return float(p1.x * p2.y - p1.y * p2.x)


def get_distance_between_two_points(one: XYPoint, two: XYPoint) -> float:
    """Calculate the distance between two XYPoints."""
    dx = one.x - two.x
    dy = one.y - two.y
    return math.sqrt(dx * dx + dy * dy)


def get_closest_point_to_line(A: XYPoint, B: XYPoint, P: XYPoint) -> XYPoint:
    """Find the closest point from P to a line defined by A and B.

    This point will be reproducible by the lamp
    as it is on the edge of the gamut.
    """
    AP = XYPoint(P.x - A.x, P.y - A.y)
    AB = XYPoint(B.x - A.x, B.y - A.y)
    ab2 = AB.x * AB.x + AB.y * AB.y
    ap_ab = AP.x * AB.x + AP.y * AB.y
    t = ap_ab / ab2

    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0

    return XYPoint(A.x + AB.x * t, A.y + AB.y * t)


def get_closest_point_to_point(
    xy_tuple: tuple[float, float], Gamut: GamutType
) -> tuple[float, float]:
    """Get the closest matching color within the gamut of the light.

    Should only be used if the supplied color is outside of the color gamut.
    """
    xy_point = XYPoint(xy_tuple[0], xy_tuple[1])

    # find the closest point on each line in the CIE 1931 'triangle'.
    pAB = get_closest_point_to_line(Gamut.red, Gamut.green, xy_point)
    pAC = get_closest_point_to_line(Gamut.blue, Gamut.red, xy_point)
    pBC = get_closest_point_to_line(Gamut.green, Gamut.blue, xy_point)

    # Get the distances per point and see which point is closer to our Point.
    dAB = get_distance_between_two_points(xy_point, pAB)
    dAC = get_distance_between_two_points(xy_point, pAC)
    dBC = get_distance_between_two_points(xy_point, pBC)

    lowest = dAB
    closest_point = pAB

    if dAC < lowest:
        lowest = dAC
        closest_point = pAC

    if dBC < lowest:
        lowest = dBC
        closest_point = pBC

    # Change the xy value to a value which is within the reach of the lamp.
    cx = closest_point.x
    cy = closest_point.y

    return (cx, cy)


def check_point_in_lamps_reach(p: tuple[float, float], Gamut: GamutType) -> bool:
    """Check if the provided XYPoint can be recreated by a Hue lamp."""
    v1 = XYPoint(Gamut.green.x - Gamut.red.x, Gamut.green.y - Gamut.red.y)
    v2 = XYPoint(Gamut.blue.x - Gamut.red.x, Gamut.blue.y - Gamut.red.y)

    q = XYPoint(p[0] - Gamut.red.x, p[1] - Gamut.red.y)
    s = cross_product(q, v2) / cross_product(v1, v2)
    t = cross_product(v1, q) / cross_product(v1, v2)

    return (s >= 0.0) and (t >= 0.0) and (s + t <= 1.0)


def check_valid_gamut(Gamut: GamutType) -> bool:
    """Check if the supplied gamut is valid."""
    # Check if the three points of the supplied gamut are not on the same line.
    v1 = XYPoint(Gamut.green.x - Gamut.red.x, Gamut.green.y - Gamut.red.y)
    v2 = XYPoint(Gamut.blue.x - Gamut.red.x, Gamut.blue.y - Gamut.red.y)
    not_on_line = cross_product(v1, v2) > 0.0001

    # Check if all six coordinates of the gamut lie between 0 and 1.
    red_valid = (
        Gamut.red.x >= 0 and Gamut.red.x <= 1 and Gamut.red.y >= 0 and Gamut.red.y <= 1
    )
    green_valid = (
        Gamut.green.x >= 0
        and Gamut.green.x <= 1
        and Gamut.green.y >= 0
        and Gamut.green.y <= 1
    )
    blue_valid = (
        Gamut.blue.x >= 0
        and Gamut.blue.x <= 1
        and Gamut.blue.y >= 0
        and Gamut.blue.y <= 1
    )

    return not_on_line and red_valid and green_valid and blue_valid

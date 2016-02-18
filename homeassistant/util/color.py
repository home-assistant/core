"""Color util methods."""


# Taken from: http://www.cse.unr.edu/~quiroz/inc/colortransforms.py
# License: Code is given as is. Use at your own risk and discretion.
# pylint: disable=invalid-name
def color_RGB_to_xy(R, G, B):
    """Convert from RGB color to XY color."""
    if R + G + B == 0:
        return 0, 0

    var_R = (R / 255.)
    var_G = (G / 255.)
    var_B = (B / 255.)

    if var_R > 0.04045:
        var_R = ((var_R + 0.055) / 1.055) ** 2.4
    else:
        var_R /= 12.92

    if var_G > 0.04045:
        var_G = ((var_G + 0.055) / 1.055) ** 2.4
    else:
        var_G /= 12.92

    if var_B > 0.04045:
        var_B = ((var_B + 0.055) / 1.055) ** 2.4
    else:
        var_B /= 12.92

    var_R *= 100
    var_G *= 100
    var_B *= 100

    # Observer. = 2 deg, Illuminant = D65
    X = var_R * 0.4124 + var_G * 0.3576 + var_B * 0.1805
    Y = var_R * 0.2126 + var_G * 0.7152 + var_B * 0.0722
    Z = var_R * 0.0193 + var_G * 0.1192 + var_B * 0.9505

    # Convert XYZ to xy, see CIE 1931 color space on wikipedia
    return X / (X + Y + Z), Y / (X + Y + Z)


# taken from
# https://github.com/benknight/hue-python-rgb-converter/blob/master/rgb_cie.py
# Copyright (c) 2014 Benjamin Knight / MIT License.
# pylint: disable=bad-builtin
def color_xy_brightness_to_RGB(vX, vY, brightness):
    """Convert from XYZ to RGB."""
    brightness /= 255.
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

    r, g, b = map(lambda x: int(x * 255), [r, g, b])

    return (r, g, b)


def rgb_hex_to_rgb_list(hex_string):
    """Return an RGB color value list from a hex color string."""
    return [int(hex_string[i:i + len(hex_string) // 3], 16)
            for i in range(0,
                           len(hex_string),
                           len(hex_string) // 3)]

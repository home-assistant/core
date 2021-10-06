"""Support for FluxLED/MagicHome lights."""
from __future__ import annotations

import homeassistant.util.color as color_util


def rgbw_brightness(
    rgbw_data: tuple[int, int, int, int],
    brightness: int | None = None,
) -> tuple[int, int, int, int]:
    """Convert rgbw to brightness."""
    h, s, v = color_util.color_RGB_to_hsv(*rgbw_data[0:3])
    color_brightness = round(v * 2.55)
    ww_brightness = rgbw_data[3]
    current_brightness = round((color_brightness + ww_brightness) / 2)

    if not brightness or brightness == current_brightness:
        return rgbw_data

    if brightness < current_brightness:
        change_brightness_pct = (current_brightness - brightness) / current_brightness
        ww_brightness = round(ww_brightness * (1 - change_brightness_pct))
        color_brightness = round(color_brightness * (1 - change_brightness_pct))

    else:
        change_brightness_pct = (brightness - current_brightness) / (
            255 - current_brightness
        )
        ww_brightness = round(
            (255 - ww_brightness) * change_brightness_pct + ww_brightness
        )
        color_brightness = round(
            (255 - color_brightness) * change_brightness_pct + color_brightness
        )

    rgb = color_util.color_hsv_to_RGB(h, s, color_brightness / 2.55)
    return (*rgb, ww_brightness)


def rgbww_brightness(
    rgbww_data: tuple[int, int, int, int, int],
    brightness: int | None = None,
) -> tuple[int, int, int, int, int]:
    """Convert rgbww to brightness."""
    h, s, v = color_util.color_RGB_to_hsv(*rgbww_data[0:3])
    color_brightness = round(v * 2.55)
    ww_brightness = rgbww_data[3]
    cw_brightness = rgbww_data[4]
    current_brightness = round((color_brightness + ww_brightness + cw_brightness) / 3)

    if not brightness or brightness == current_brightness:
        return rgbww_data

    if brightness < current_brightness:
        change_brightness_pct = (current_brightness - brightness) / current_brightness
        ww_brightness = round(ww_brightness * (1 - change_brightness_pct))
        color_brightness = round(color_brightness * (1 - change_brightness_pct))
        cw_brightness = round(cw_brightness * (1 - change_brightness_pct))
    else:
        change_brightness_pct = (brightness - current_brightness) / (
            255 - current_brightness
        )
        ww_brightness = round(
            (255 - ww_brightness) * change_brightness_pct + ww_brightness
        )
        color_brightness = round(
            (255 - color_brightness) * change_brightness_pct + color_brightness
        )
        cw_brightness = round(
            (255 - cw_brightness) * change_brightness_pct + cw_brightness
        )

    rgb = color_util.color_hsv_to_RGB(h, s, color_brightness / 2.55)
    return (*rgb, ww_brightness, cw_brightness)

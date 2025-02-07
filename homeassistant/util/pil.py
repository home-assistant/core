"""PIL utilities.

Can only be used by integrations that have pillow in their requirements.
"""

from __future__ import annotations

from PIL.ImageDraw import ImageDraw


def draw_box(
    draw: ImageDraw,
    box: tuple[float, float, float, float],
    img_width: int,
    img_height: int,
    text: str = "",
    color: tuple[int, int, int] = (255, 255, 0),
) -> None:
    """Draw a bounding box on and image.

    The bounding box is defined by the tuple (y_min, x_min, y_max, x_max)
    where the coordinates are floats in the range [0.0, 1.0] and
    relative to the width and height of the image.

    For example, if an image is 100 x 200 pixels (height x width) and the bounding
    box is `(0.1, 0.2, 0.5, 0.9)`, the upper-left and bottom-right coordinates of
    the bounding box will be `(40, 10)` to `(180, 50)` (in (x,y) coordinates).
    """

    line_width = 3
    font_height = 20
    y_min, x_min, y_max, x_max = box
    (left, right, top, bottom) = (
        x_min * img_width,
        x_max * img_width,
        y_min * img_height,
        y_max * img_height,
    )
    draw.line(
        [(left, top), (left, bottom), (right, bottom), (right, top), (left, top)],
        width=line_width,
        fill=color,
    )
    if text:
        draw.text(
            (left + line_width, abs(top - line_width - font_height)),
            text,
            fill=color,
            font_size=font_height,
        )

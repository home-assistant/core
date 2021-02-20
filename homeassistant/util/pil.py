"""PIL utilities.

Can only be used by integrations that have pillow in their requirements.
"""
from typing import Tuple

from PIL import ImageDraw, ImageFont


def draw_box(
    draw: ImageDraw,
    box: Tuple[float, float, float, float],
    img_width: int,
    img_height: int,
    text: str = "",
    color: Tuple[int, int, int] = (255, 255, 0),
    textbox: bool = False,
    font: ImageFont = None,
    font_color: Tuple[int, int, int] = (255, 255, 255),
) -> None:
    """
    Draw a bounding box on and image.

    The bounding box is defined by the tuple (y_min, x_min, y_max, x_max)
    where the coordinates are floats in the range [0.0, 1.0] and
    relative to the width and height of the image.

    For example, if an image is 100 x 200 pixels (height x width) and the bounding
    box is `(0.1, 0.2, 0.5, 0.9)`, the upper-left and bottom-right coordinates of
    the bounding box will be `(40, 10)` to `(180, 50)` (in (x,y) coordinates).

    If a text is provided and textbox=false the text is drawn in the same color as the box.
    If textbox=true a rectangle of the same color as the box is drawn above the box and the
    text is placed inside the rectangle using the provided font_color
    """

    line_width = 3
    font_height = 8
    text_color = color
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

        if font is None:
            font = draw.getfont()
        text_size = font.getsize(text)
        if textbox:
            button_size = (text_size[0] + 4, text_size[1] + 4)
            xloc = int(left)
            yloc = int(abs(top - button_size[1]))
            shape = [xloc, yloc, button_size[0] + xloc, button_size[1] + yloc]
            draw.rectangle(shape, fill=color, outline=color)
            text_color = font_color
        font_height = text_size[1]
        draw.text(
            (left + line_width, abs(top - line_width - font_height) + 1),
            text,
            font=font,
            fill=text_color,
        )

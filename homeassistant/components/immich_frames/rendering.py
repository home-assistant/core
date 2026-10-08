"""Render Immich photos to the Home Assistant frame output contract."""

from io import BytesIO
from typing import cast

from PIL import Image, ImageOps

from .const import DEFAULT_PHOTO_FIT, DEFAULT_SCREEN_SHAPE, PHOTO_FIT_CROP, SCREEN_SIZES


def image_size(payload: bytes) -> tuple[int, int]:
    """Return decoded dimensions after applying EXIF orientation."""
    with Image.open(BytesIO(payload)) as image:
        image.load()
        width, height = image.size
        if image.getexif().get(274) in (5, 6, 7, 8):
            return height, width
        return width, height


def _background_colour(image: Image.Image) -> tuple[int, int, int]:
    """Sample a photo colour for full-image padding."""
    step_x = max(1, image.width // 20)
    step_y = max(1, image.height // 20)
    red = green = blue = total_weight = 0
    for y in range(step_y // 2, image.height, step_y):
        for x in range(step_x // 2, image.width, step_x):
            r, g, b = cast(tuple[int, int, int], image.getpixel((x, y)))
            saturation = max(r, g, b) - min(r, g, b)
            weight = saturation * saturation + 1
            red += r * weight
            green += g * weight
            blue += b * weight
            total_weight += weight
    return (
        red // total_weight // 2,
        green // total_weight // 2,
        blue // total_weight // 2,
    )


def render(
    payloads: list[bytes],
    screen_shape: str = DEFAULT_SCREEN_SHAPE,
    fit: str = DEFAULT_PHOTO_FIT,
) -> tuple[bytes, str]:
    """Render one or two photos into an exact-size JPEG frame."""
    canvas_size = SCREEN_SIZES.get(screen_shape, SCREEN_SIZES[DEFAULT_SCREEN_SHAPE])
    images: list[Image.Image] = []
    try:
        images.extend(
            ImageOps.exif_transpose(Image.open(BytesIO(payload))).convert("RGB")
            for payload in payloads
        )

        def tile(image: Image.Image, size: tuple[int, int]) -> Image.Image:
            if fit == PHOTO_FIT_CROP:
                return ImageOps.fit(image, size, Image.Resampling.LANCZOS)
            contained = ImageOps.contain(image, size, Image.Resampling.LANCZOS)
            result = Image.new("RGB", size, _background_colour(image))
            result.paste(
                contained,
                ((size[0] - contained.width) // 2, (size[1] - contained.height) // 2),
            )
            return result

        if len(images) == 1:
            canvas = tile(images[0], canvas_size)
            layout = "single"
        else:
            canvas = Image.new("RGB", canvas_size, "black")
            divider = canvas.width // 2
            tiles = ((0, divider), (divider + 1, canvas.width - divider - 1))
            for image, (left, width) in zip(images[:2], tiles, strict=True):
                canvas.paste(tile(image, (width, canvas.height)), (left, 0))
            layout = "side_by_side"

        output = BytesIO()
        canvas.save(output, "JPEG", quality=95, subsampling=0, optimize=True)
        return output.getvalue(), layout
    finally:
        for image in images:
            image.close()

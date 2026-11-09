"""Validate the brand images an integration ships in its brand folder."""

from pathlib import Path
import struct

from .model import Config, Integration

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# Signature, then the IHDR chunk: length, type, 13 bytes of data and its CRC.
PNG_HEADER_SIZE = 33
IHDR_START = b"\x00\x00\x00\x0dIHDR"

# Mirrors homeassistant.components.brands.const; the package can't import Core, and a
# Core test keeps both in sync.
ALLOWED_IMAGES = frozenset(
    {
        "icon.png",
        "logo.png",
        "icon@2x.png",
        "logo@2x.png",
        "dark_icon.png",
        "dark_logo.png",
        "dark_icon@2x.png",
        "dark_logo@2x.png",
    }
)
IMAGE_FALLBACKS = {
    "logo.png": ["icon.png"],
    "icon@2x.png": ["icon.png"],
    "logo@2x.png": ["logo.png", "icon.png"],
    "dark_icon.png": ["icon.png"],
    "dark_logo.png": ["dark_icon.png", "logo.png", "icon.png"],
    "dark_icon@2x.png": ["icon@2x.png", "icon.png"],
    "dark_logo@2x.png": ["dark_icon@2x.png", "logo@2x.png", "logo.png", "icon.png"],
}

# Same size rules as the home-assistant/brands repository; dark_ variants share them.
ICON_SIZE = {"icon.png": 256, "icon@2x.png": 512}
LOGO_SHORTEST_SIDE = {"logo.png": (128, 256), "logo@2x.png": (256, 512)}


def _report(integration: Integration, message: str) -> None:
    """Report a problem: an error for core, a warning for custom integrations.

    Custom integrations get warnings so existing repositories don't start failing.
    """
    integration.add_warning_or_error(not integration.core, "brand_images", message)


def _png_size(path: Path) -> tuple[int, int] | None:
    """Return the width and height from a PNG header, or None if it is no PNG."""
    with path.open("rb") as file:
        header = file.read(PNG_HEADER_SIZE)
    if (
        len(header) < PNG_HEADER_SIZE
        or header[:8] != PNG_SIGNATURE
        or header[8:16] != IHDR_START
    ):
        return None
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def _validate_size(integration: Integration, image: str, size: tuple[int, int]) -> None:
    """Validate the dimensions of a brand image."""
    base = image.removeprefix("dark_")
    width, height = size
    if base in ICON_SIZE:
        expected = ICON_SIZE[base]
        if size != (expected, expected):
            _report(
                integration,
                f"brand/{image} is {width}x{height}, but must be {expected}x{expected}",
            )
        return
    low, high = LOGO_SHORTEST_SIDE[base]
    if not low <= min(size) <= high:
        _report(
            integration,
            f"brand/{image} is {width}x{height}, but its shortest side must be"
            f" between {low} and {high} pixels",
        )


def _served(images: dict[str, Path], image: str) -> Path | None:
    """Return the file the brands integration serves for an image, if any."""
    return next(
        (
            images[name]
            for name in (image, *IMAGE_FALLBACKS.get(image, ()))
            if name in images
        ),
        None,
    )


def _redundant_fallback(images: dict[str, Path], image: str) -> str | None:
    """Return the fallback an image duplicates, if removing it changes nothing."""
    fallback = next(
        (name for name in IMAGE_FALLBACKS.get(image, ()) if name in images), None
    )
    if fallback is None or images[fallback].read_bytes() != images[image].read_bytes():
        return None
    # An @2x image requires its normal-resolution companion.
    if image.replace(".png", "@2x.png") in images:
        return None
    remaining = {name: path for name, path in images.items() if name != image}
    for other in sorted(ALLOWED_IMAGES):
        before, after = _served(images, other), _served(remaining, other)
        if before and after and before.read_bytes() != after.read_bytes():
            return None
    return fallback


def _validate_brand_folder(integration: Integration, brand_dir: Path) -> None:
    """Validate the brand folder of an integration."""
    images: dict[str, Path] = {}
    for path in sorted(brand_dir.iterdir()):
        if path.is_file():
            images[path.name] = path
        else:
            _report(integration, f"brand/{path.name} is not a file")

    for name in sorted(images.keys() - ALLOWED_IMAGES):
        _report(
            integration,
            f"brand/{name} is not a brand image Home Assistant uses, allowed are:"
            f" {', '.join(sorted(ALLOWED_IMAGES))}",
        )

    for image in sorted(images.keys() & ALLOWED_IMAGES):
        if (size := _png_size(images[image])) is None:
            _report(integration, f"brand/{image} is not a PNG image")
            continue
        _validate_size(integration, image, size)

        if "@2x" in image and image.replace("@2x", "") not in images:
            _report(
                integration,
                f"brand/{image} is provided, but brand/{image.replace('@2x', '')}"
                " is missing",
            )

        if (fallback := _redundant_fallback(images, image)) is not None:
            _report(
                integration,
                f"brand/{image} is identical to brand/{fallback}, which is used"
                f" when brand/{image} is missing, remove brand/{image}",
            )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate the brand folders of all integrations."""
    for integration in integrations.values():
        if (brand_dir := integration.path / "brand").is_dir():
            _validate_brand_folder(integration, brand_dir)

"""The QR code component."""

import io
from pathlib import Path

from PIL import Image

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

DOMAIN = "qrcode"
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the QR Code component."""
    return True


def decode_qr_image(image: bytes | Path | str) -> list[str]:
    """Decode QR code string payloads from an image in bytes or file path."""
    from pyzbar import pyzbar  # noqa: PLC0415

    if isinstance(image, (bytes, bytearray)):
        stream = io.BytesIO(image)
        with Image.open(stream) as img:
            rgb_img = img.convert("RGB")
            decoded_objects = pyzbar.decode(rgb_img)
    else:
        with Image.open(image) as img:
            rgb_img = img.convert("RGB")
            decoded_objects = pyzbar.decode(rgb_img)

    results: list[str] = []
    for obj in decoded_objects:
        if obj.data:
            try:
                results.append(obj.data.decode("utf-8"))
            except UnicodeDecodeError:
                results.append(obj.data.decode("utf-8", errors="replace"))
    return results

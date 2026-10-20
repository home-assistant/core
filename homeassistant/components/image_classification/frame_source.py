"""Frames from the source camera and the region the sensor watches."""

from collections.abc import Mapping
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from homeassistant.components.camera import async_get_image
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import CONF_BOTTOM, CONF_LEFT, CONF_RIGHT, CONF_TOP, DOMAIN

# Longer side taught frames and previews are scaled down to.
FRAME_SIDE = 1024


class FrameUnavailable(HomeAssistantError):
    """The camera did not return a frame."""


class InvalidFrame(Exception):
    """The frame could not be decoded."""


async def async_fetch_frame(hass: HomeAssistant, entity_id: str) -> bytes:
    """Return the current frame of a camera."""
    try:
        image = await async_get_image(hass, entity_id)
    except HomeAssistantError as err:
        raise FrameUnavailable(
            translation_domain=DOMAIN,
            translation_key="camera_unavailable",
            translation_placeholders={"entity_id": entity_id, "error": str(err)},
        ) from err
    return image.content


def load_image(data: bytes) -> Image.Image:
    """Decode a frame to RGB with the longer side at most FRAME_SIDE; blocking."""
    try:
        encoded = Image.open(BytesIO(data))
        width, height = encoded.size
        if (scale := FRAME_SIDE / max(width, height)) < 1:
            # Decoding a JPEG at a reduced scale is much cheaper than in full.
            encoded.draft("RGB", (int(width * scale), int(height * scale)))
        image = encoded.convert("RGB")
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as err:
        raise InvalidFrame(str(err)) from err
    image.thumbnail((FRAME_SIDE, FRAME_SIDE))
    return image


def encode_jpeg(image: Image.Image, quality: int) -> bytes:
    """Encode an image as JPEG; blocking."""
    buffer = BytesIO()
    image.save(buffer, "JPEG", quality=quality)
    return buffer.getvalue()


def prepare_frame(data: bytes) -> bytes:
    """Return a camera frame as the JPEG stored when it is taught; blocking."""
    return encode_jpeg(load_image(data), quality=95)


def region_error(region: Mapping[str, float]) -> str | None:
    """Return the error key when a region in percent is empty."""
    if region[CONF_LEFT] >= region[CONF_RIGHT]:
        return "invalid_horizontal_range"
    if region[CONF_TOP] >= region[CONF_BOTTOM]:
        return "invalid_vertical_range"
    return None


def region_to_fractions(region: Mapping[str, float]) -> dict[str, float]:
    """Convert a stored region in percent to fractions of the frame."""
    return {side: value / 100 for side, value in region.items()}

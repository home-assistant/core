"""Frames from the source camera."""

from homeassistant.components.camera import async_get_image
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


class FrameUnavailable(HomeAssistantError):
    """The camera did not return a frame."""


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

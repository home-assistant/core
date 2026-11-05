"""Camera helper functions."""

from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DATA_COMPONENT, DOMAIN, CameraEntityFeature

if TYPE_CHECKING:
    from . import Camera


def get_camera_from_entity_id(hass: HomeAssistant, entity_id: str) -> Camera:
    """Get camera component from entity_id."""
    component = hass.data.get(DATA_COMPONENT)
    if component is None:
        raise HomeAssistantError("Camera integration not set up")

    if (camera := component.get_entity(entity_id)) is None:
        raise HomeAssistantError("Camera not found")

    if not camera.is_on:
        raise HomeAssistantError("Camera is off")

    return camera


async def async_get_stream_image(
    camera: Camera,
    width: int | None = None,
    height: int | None = None,
    wait_for_next_keyframe: bool = False,
) -> bytes | None:
    """Return a still image from the camera's stream."""
    if (provider := camera.webrtc_provider) and (
        image := await provider.async_get_image(camera, width=width, height=height)
    ) is not None:
        return image
    if not camera.stream and CameraEntityFeature.STREAM in camera.supported_features:
        camera.stream = await camera.async_create_stream()
    if camera.stream:
        return await camera.stream.async_get_image(
            width=width, height=height, wait_for_next_keyframe=wait_for_next_keyframe
        )
    return None


async def async_stream_endpoint_url(
    hass: HomeAssistant, camera: Camera, fmt: str
) -> str:
    """Start the camera stream and return its endpoint URL."""
    stream = await camera.async_create_stream()
    if not stream:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="stream_not_supported",
            translation_placeholders={"entity_id": camera.entity_id},
        )

    stream.add_provider(fmt)
    await stream.start()
    return stream.endpoint_url(fmt)

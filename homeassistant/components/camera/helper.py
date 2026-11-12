"""Camera helper functions."""

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import (
    CAMERA_PAST_IMAGE_TIMEOUT,
    DATA_COMPONENT,
    DOMAIN,
    CameraEntityFeature,
)

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


async def async_get_past_image(camera: Camera, timestamp: datetime) -> bytes:
    """Return a JPEG from the camera's recorded history.

    A naive timestamp is local time. A camera that is off gives no image,
    like the live one.
    """
    if CameraEntityFeature.PAST_IMAGE not in camera.supported_features:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="past_image_not_supported",
            translation_placeholders={"entity_id": camera.entity_id},
        )
    if not camera.is_on:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="camera_off",
            translation_placeholders={"entity_id": camera.entity_id},
        )
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=dt_util.get_default_time_zone())
    if timestamp > dt_util.utcnow():
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="past_image_in_future",
            translation_placeholders={"timestamp": timestamp.isoformat()},
        )
    try:
        async with asyncio.timeout(CAMERA_PAST_IMAGE_TIMEOUT):
            return await camera.async_camera_image_past(timestamp)
    except TimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="snapshot_timeout",
            translation_placeholders={"timeout": str(CAMERA_PAST_IMAGE_TIMEOUT)},
        ) from err


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

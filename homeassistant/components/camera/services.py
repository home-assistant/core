"""Services for the camera integration."""

import asyncio
import os
from typing import TYPE_CHECKING

import probatio

from homeassistant.components.media_player import (
    DOMAIN as MP_DOMAIN,
    MediaPlayerService,
    MediaPlayerServiceArgument,
)
from homeassistant.components.stream import FORMAT_CONTENT_TYPE, OUTPUT_FORMATS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.network import get_url
from homeassistant.helpers.os_error import os_write_error
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import VolDictType

from .const import (
    CAMERA_IMAGE_TIMEOUT,
    DATA_COMPONENT,
    DOMAIN,
    CameraService,
    CameraServiceArgument,
)
from .helper import async_get_stream_image, async_stream_endpoint_url

if TYPE_CHECKING:
    from .entity import Camera

CAMERA_SERVICE_SNAPSHOT: VolDictType = {
    probatio.Required(CameraServiceArgument.FILENAME): cv.template
}


CAMERA_SERVICE_PLAY_STREAM: VolDictType = {
    probatio.Required(CameraServiceArgument.MEDIA_PLAYER): cv.entities_domain(
        MP_DOMAIN
    ),
    probatio.Optional(CameraServiceArgument.FORMAT, default="hls"): probatio.In(
        OUTPUT_FORMATS
    ),
}


CAMERA_SERVICE_RECORD: VolDictType = {
    probatio.Required(CameraServiceArgument.FILENAME): cv.template,
    probatio.Optional(CameraServiceArgument.DURATION, default=30): probatio.Coerce(int),
    probatio.Optional(CameraServiceArgument.LOOKBACK, default=0): probatio.Coerce(int),
}


async def _async_handle_snapshot_service(
    camera: Camera, service_call: ServiceCall
) -> None:
    """Handle snapshot services calls."""
    hass = camera.hass
    filename: Template = service_call.data[CameraServiceArgument.FILENAME]

    snapshot_file = filename.async_render()

    # check if we allow to access to that file
    if not hass.config.is_allowed_path(snapshot_file):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="path_not_allowed",
            translation_placeholders={"filename": snapshot_file},
        )

    try:
        async with asyncio.timeout(CAMERA_IMAGE_TIMEOUT):
            image = (
                await async_get_stream_image(camera, wait_for_next_keyframe=True)
                if camera.use_stream_for_stills
                else await camera.async_camera_image()
            )
    except TimeoutError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="snapshot_timeout",
            translation_placeholders={"timeout": str(CAMERA_IMAGE_TIMEOUT)},
        ) from err

    if image is None:
        return

    def _write_image(to_file: str, image_data: bytes) -> None:
        """Executor helper to write image."""
        os.makedirs(os.path.dirname(to_file), exist_ok=True)
        with open(to_file, "wb") as img_file:
            img_file.write(image_data)

    try:
        await hass.async_add_executor_job(_write_image, snapshot_file, image)
    except OSError as err:
        raise os_write_error(err, snapshot_file) from err


async def _async_handle_play_stream_service(
    camera: Camera, service_call: ServiceCall
) -> None:
    """Handle play stream services calls."""
    hass = camera.hass
    fmt = service_call.data[CameraServiceArgument.FORMAT]
    url = await async_stream_endpoint_url(camera.hass, camera, fmt)
    url = f"{get_url(hass)}{url}"

    await hass.services.async_call(
        MP_DOMAIN,
        MediaPlayerService.PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: service_call.data[CameraServiceArgument.MEDIA_PLAYER],
            MediaPlayerServiceArgument.MEDIA_CONTENT_ID: url,
            MediaPlayerServiceArgument.MEDIA_CONTENT_TYPE: FORMAT_CONTENT_TYPE[fmt],
        },
        blocking=True,
        context=service_call.context,
    )


async def _async_handle_record_service(
    camera: Camera, service_call: ServiceCall
) -> None:
    """Handle stream recording service calls."""
    stream = await camera.async_create_stream()

    if not stream:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="record_not_supported",
            translation_placeholders={"entity_id": camera.entity_id},
        )

    filename = service_call.data[CameraServiceArgument.FILENAME]
    video_path = filename.async_render()

    await stream.async_record(
        video_path,
        duration=service_call.data[CameraServiceArgument.DURATION],
        lookback=service_call.data[CameraServiceArgument.LOOKBACK],
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the camera services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        CameraService.ENABLE_MOTION_DETECTION, None, "async_enable_motion_detection"
    )
    component.async_register_entity_service(
        CameraService.DISABLE_MOTION_DETECTION, None, "async_disable_motion_detection"
    )
    component.async_register_entity_service(
        CameraService.TURN_OFF, None, "async_turn_off"
    )
    component.async_register_entity_service(
        CameraService.TURN_ON, None, "async_turn_on"
    )
    component.async_register_entity_service(
        CameraService.SNAPSHOT, CAMERA_SERVICE_SNAPSHOT, _async_handle_snapshot_service
    )
    component.async_register_entity_service(
        CameraService.PLAY_STREAM,
        CAMERA_SERVICE_PLAY_STREAM,
        _async_handle_play_stream_service,
    )
    component.async_register_entity_service(
        CameraService.RECORD, CAMERA_SERVICE_RECORD, _async_handle_record_service
    )

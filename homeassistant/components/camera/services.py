"""Services for the camera integration."""

import asyncio
import os
from typing import TYPE_CHECKING

import probatio

from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    DOMAIN as MP_DOMAIN,
    SERVICE_PLAY_MEDIA,
)
from homeassistant.components.stream import FORMAT_CONTENT_TYPE, OUTPUT_FORMATS
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_FILENAME,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.network import get_url
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import VolDictType

from .const import (
    ATTR_FILENAME,
    ATTR_FORMAT,
    ATTR_MEDIA_PLAYER,
    CAMERA_IMAGE_TIMEOUT,
    CONF_DURATION,
    CONF_LOOKBACK,
    DATA_COMPONENT,
    SERVICE_DISABLE_MOTION,
    SERVICE_ENABLE_MOTION,
    SERVICE_PLAY_STREAM,
    SERVICE_RECORD,
    SERVICE_SNAPSHOT,
)
from .helper import async_get_stream_image, async_stream_endpoint_url

if TYPE_CHECKING:
    from . import Camera

CAMERA_SERVICE_SNAPSHOT: VolDictType = {probatio.Required(ATTR_FILENAME): cv.template}


CAMERA_SERVICE_PLAY_STREAM: VolDictType = {
    probatio.Required(ATTR_MEDIA_PLAYER): cv.entities_domain(MP_DOMAIN),
    probatio.Optional(ATTR_FORMAT, default="hls"): probatio.In(OUTPUT_FORMATS),
}


CAMERA_SERVICE_RECORD: VolDictType = {
    probatio.Required(CONF_FILENAME): cv.template,
    probatio.Optional(CONF_DURATION, default=30): probatio.Coerce(int),
    probatio.Optional(CONF_LOOKBACK, default=0): probatio.Coerce(int),
}


async def _async_handle_snapshot_service(
    camera: Camera, service_call: ServiceCall
) -> None:
    """Handle snapshot services calls."""
    hass = camera.hass
    filename: Template = service_call.data[ATTR_FILENAME]

    snapshot_file = filename.async_render()

    # check if we allow to access to that file
    if not hass.config.is_allowed_path(snapshot_file):
        raise HomeAssistantError(
            f"Cannot write `{snapshot_file}`, no access to path;"
            " `allowlist_external_dirs` may need to be adjusted"
            " in `configuration.yaml`"
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
            f"Unable to get snapshot: Timed out after {CAMERA_IMAGE_TIMEOUT} seconds"
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
        raise HomeAssistantError(f"Can't write image to file: {err}") from err


async def _async_handle_play_stream_service(
    camera: Camera, service_call: ServiceCall
) -> None:
    """Handle play stream services calls."""
    hass = camera.hass
    fmt = service_call.data[ATTR_FORMAT]
    url = await async_stream_endpoint_url(camera.hass, camera, fmt)
    url = f"{get_url(hass)}{url}"

    await hass.services.async_call(
        MP_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: service_call.data[ATTR_MEDIA_PLAYER],
            ATTR_MEDIA_CONTENT_ID: url,
            ATTR_MEDIA_CONTENT_TYPE: FORMAT_CONTENT_TYPE[fmt],
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
        raise HomeAssistantError(f"{camera.entity_id} does not support record service")

    filename = service_call.data[CONF_FILENAME]
    video_path = filename.async_render()

    await stream.async_record(
        video_path,
        duration=service_call.data[CONF_DURATION],
        lookback=service_call.data[CONF_LOOKBACK],
    )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the camera services."""
    component = hass.data[DATA_COMPONENT]

    component.async_register_entity_service(
        SERVICE_ENABLE_MOTION, None, "async_enable_motion_detection"
    )
    component.async_register_entity_service(
        SERVICE_DISABLE_MOTION, None, "async_disable_motion_detection"
    )
    component.async_register_entity_service(SERVICE_TURN_OFF, None, "async_turn_off")
    component.async_register_entity_service(SERVICE_TURN_ON, None, "async_turn_on")
    component.async_register_entity_service(
        SERVICE_SNAPSHOT, CAMERA_SERVICE_SNAPSHOT, _async_handle_snapshot_service
    )
    component.async_register_entity_service(
        SERVICE_PLAY_STREAM,
        CAMERA_SERVICE_PLAY_STREAM,
        _async_handle_play_stream_service,
    )
    component.async_register_entity_service(
        SERVICE_RECORD, CAMERA_SERVICE_RECORD, _async_handle_record_service
    )

"""Services for the image integration."""

import asyncio
import os
from typing import TYPE_CHECKING

import probatio

from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.os_error import os_error_translation_key
from homeassistant.helpers.typing import VolDictType

from .const import (
    ATTR_FILENAME,
    DATA_COMPONENT,
    DOMAIN,
    IMAGE_TIMEOUT,
    SERVICE_SNAPSHOT,
)

if TYPE_CHECKING:
    from . import ImageEntity

IMAGE_SERVICE_SNAPSHOT: VolDictType = {probatio.Required(ATTR_FILENAME): cv.string}


async def _async_handle_snapshot_service(
    image: ImageEntity, service_call: ServiceCall
) -> None:
    """Handle snapshot services calls."""
    hass = image.hass
    snapshot_file: str = service_call.data[ATTR_FILENAME]

    # check if we allow to access to that file
    if not hass.config.is_allowed_path(snapshot_file):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="path_not_allowed",
            translation_placeholders={"filename": snapshot_file},
        )

    async with asyncio.timeout(IMAGE_TIMEOUT):
        image_data = await image.async_image()

    if image_data is None:
        return

    def _write_image(to_file: str, image_data: bytes) -> None:
        """Executor helper to write image."""
        os.makedirs(os.path.dirname(to_file), exist_ok=True)
        with open(to_file, "wb") as img_file:
            img_file.write(image_data)

    try:
        await hass.async_add_executor_job(_write_image, snapshot_file, image_data)
    except OSError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key=os_error_translation_key(err),
            translation_placeholders={"path": snapshot_file},
        ) from err


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the image services."""
    hass.data[DATA_COMPONENT].async_register_entity_service(
        SERVICE_SNAPSHOT, IMAGE_SERVICE_SNAPSHOT, _async_handle_snapshot_service
    )

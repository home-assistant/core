"""Support for SwitchBot Cloud services."""

from enum import StrEnum
from logging import getLogger

import probatio
from switchbot_api import ArtFrameCommands

from homeassistant.const import CommonServiceArgument
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import DOMAIN

_LOGGER = getLogger(__name__)


class SwitchBotCloudService(StrEnum):
    """Store keys for SwitchBot Cloud services."""

    UPLOAD_ART_FRAME_IMAGE = "upload_art_frame_image"


class SwitchBotCloudServiceArgument(StrEnum):
    """Store keys for SwitchBot Cloud service arguments."""

    IMAGE_URL = "image_url"


UPLOAD_IMAGE_SCHEMA = probatio.Schema(
    {
        probatio.Required(CommonServiceArgument.DEVICE_ID): probatio.All(
            probatio.EnsureList(), [cv.string], probatio.NonEmpty()
        ),
        probatio.Required(SwitchBotCloudServiceArgument.IMAGE_URL): cv.url,
    }
)


async def handle_upload_image(call: ServiceCall) -> None:
    """Handle Ai Art Frame Upload Image."""
    hass = call.hass
    image_url = call.data[SwitchBotCloudServiceArgument.IMAGE_URL]
    device_ids = call.data.get(CommonServiceArgument.DEVICE_ID, [])

    for ha_device_id in device_ids:
        device, config_entry = service.async_get_device_and_config_entry(
            hass, DOMAIN, ha_device_id
        )

        device_mac = next(
            (iid[1] for iid in device.identifiers if iid[0] == DOMAIN), None
        )
        if device_mac is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_valid_mac_address",
            )

        await config_entry.runtime_data.api.send_command(
            device_id=device_mac,
            command=ArtFrameCommands.UPLOAD.value,
            command_type="command",
            parameters={"imageUrl": image_url},
        )


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the SwitchBot Cloud services."""
    hass.services.async_register(
        DOMAIN,
        SwitchBotCloudService.UPLOAD_ART_FRAME_IMAGE,
        handle_upload_image,
        schema=UPLOAD_IMAGE_SCHEMA,
    )

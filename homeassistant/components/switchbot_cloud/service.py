"""SwitchBot Cloud Custom Service."""

from logging import getLogger

from switchbot_api import ArtFrameCommands
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, service

from .const import AI_ART_FRAME_UPLOAD_IMAGE_SERVICE, DOMAIN

_LOGGER = getLogger(__name__)


UPLOAD_IMAGE_SCHEMA = vol.Schema(
    {
        vol.Required("device_id"): vol.All(
            cv.ensure_list, [cv.string], vol.Length(min=1)
        ),
        vol.Required("image_url"): cv.url,
    }
)


async def handle_upload_image(call: ServiceCall) -> None:
    """Handle Ai Art Frame Upload Image."""
    hass = call.hass
    image_url = call.data["image_url"]
    device_ids = call.data.get("device_id", [])

    for ha_device_id in device_ids:
        device, config_entry = service.async_get_device_and_config_entry(
            hass, DOMAIN, ha_device_id
        )

        device_mac = next(
            (iid[1] for iid in device.identifiers if iid[0] == DOMAIN), None
        )
        if device_mac is None:
            raise ServiceValidationError("No valid MAC address obtained.")

        await config_entry.runtime_data.api.send_command(
            device_id=device_mac,
            command=ArtFrameCommands.UPLOAD.value,
            command_type="command",
            parameters={"imageUrl": image_url},
        )


def async_register_services(hass: HomeAssistant) -> None:
    """Async register services."""
    hass.services.async_register(
        DOMAIN,
        AI_ART_FRAME_UPLOAD_IMAGE_SERVICE,
        handle_upload_image,
        schema=UPLOAD_IMAGE_SCHEMA,
    )

"""SwitchBot Cloud Custom Service."""

from logging import getLogger
from typing import Any

from switchbot_api import ArtFrameCommands, SwitchBotAPI
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import AI_ART_FRAME_UPLOAD_IMAGE_SERVICE, DOMAIN

_LOGGER = getLogger(__name__)


UPLOAD_IMAGE_SCHEMA = vol.Schema(
    {
        vol.Required("image_url"): cv.url,
    },
    extra=vol.ALLOW_EXTRA,
)


def _get_api(
    entries: list[Any], device_model: str, target_entry_id: str
) -> SwitchBotAPI:
    """Get device's api."""
    for entry in entries:
        if target_entry_id == entry.entry_id:
            return entry.runtime_data.api
    raise ServiceValidationError(f"Device {device_model} Is Not Support This Service")


async def handle_upload_image(call: ServiceCall) -> None:
    """Handle Ai Art Frame Upload Image."""
    hass = call.hass
    image_url = call.data["image_url"]
    device_ids = call.data.get("device_id", [])
    if isinstance(device_ids, str):
        device_ids = [device_ids]
    if not device_ids:
        raise ServiceValidationError("Target Device ID is required")
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        raise ServiceValidationError("switchbot_cloud is not configured")
    dev_reg = dr.async_get(hass)

    for ha_device_id in device_ids:
        device = dev_reg.async_get(ha_device_id)
        if device is None:
            continue
        device_mac = next(iter(device.identifiers))[1]
        entry_id = next(iter(device.config_entries))
        model = device.model

        if model != "AI Art Frame":
            _LOGGER.error(
                "No loaded config entry found for device %s mac = %s", model, device_mac
            )
            continue

        api = _get_api(entries, model, entry_id)
        await api.send_command(
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

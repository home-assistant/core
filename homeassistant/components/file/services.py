"""File Service calls."""

from __future__ import annotations

import json
import logging

import anyio
import voluptuous as vol
import yaml

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import ATTR_FILE_ENCODING, ATTR_FILE_NAME, DOMAIN, SERVICE_READ_FILE

LOGGER = logging.getLogger(__name__)


def async_register_services(hass: HomeAssistant) -> None:
    """Register services for Hue integration."""

    if not hass.services.has_service(DOMAIN, SERVICE_READ_FILE):
        hass.services.async_register(
            DOMAIN,
            SERVICE_READ_FILE,
            read_file,
            schema=vol.Schema(
                {
                    vol.Required(ATTR_FILE_NAME): cv.string,
                    vol.Required(ATTR_FILE_ENCODING): cv.string,
                }
            ),
            supports_response=SupportsResponse.ONLY,
        )


async def read_file(call: ServiceCall, skip_reload=True) -> dict:
    """Handle activation of Hue scene."""
    # Get parameters
    file_name = call.data[ATTR_FILE_NAME]
    file_encoding = call.data[ATTR_FILE_ENCODING].lower()
    if not call.hass.config.is_allowed_path(file_name):
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="no_access_to_path",
            translation_placeholders={"filename": file_name},
        )
    try:
        async with await anyio.open_file(file_name, encoding="utf-8") as file:
            file_content = await file.read()
        if file_encoding == "json":
            return json.loads(file_content)
        if file_encoding == "yaml":
            yaml_content = yaml.safe_load(file_content)
            if isinstance(yaml_content, dict):
                return yaml_content
            if isinstance(yaml_content, list):
                return {"list": yaml_content}
            raise HomeAssistantError(
                f"Unsupported YAML content type: {type(yaml_content)}"
            )

    except json.JSONDecodeError as err:
        raise HomeAssistantError(f"Error reading JSON file: {err}") from err
    raise ServiceValidationError(f"Unsupported file encoding: {file_encoding}")

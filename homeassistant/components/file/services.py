"""File Service calls."""

import json

import anyio
import voluptuous as vol
import yaml

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import ATTR_FILE_ENCODING, ATTR_FILE_NAME, DOMAIN, SERVICE_READ_FILE


def async_register_services(hass: HomeAssistant) -> None:
    """Register services for File integration."""

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


async def read_file(call: ServiceCall) -> dict:
    """Handle read_file service call."""
    file_name = call.data[ATTR_FILE_NAME]
    file_encoding = call.data[ATTR_FILE_ENCODING].lower()

    if not await call.hass.async_add_executor_job(
        call.hass.config.is_allowed_path, file_name
    ):
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
            return {"yaml": yaml_content}
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unsupported_file_encoding",
            translation_placeholders={"filename": file_name, "encoding": file_encoding},
        )

    except FileNotFoundError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="file_not_found",
            translation_placeholders={"filename": file_name},
        ) from err
    except (json.JSONDecodeError, yaml.YAMLError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="file_decoding",
            translation_placeholders={"filename": file_name, "encoding": file_encoding},
        ) from err

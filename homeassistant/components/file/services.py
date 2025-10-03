"""File Service calls."""

from collections.abc import Callable
import json

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


ENCODING_LOADERS: dict[str, tuple[Callable, type[Exception]]] = {
    "json": (json.loads, json.JSONDecodeError),
    "yaml": (yaml.safe_load, yaml.YAMLError),
}


def read_file(call: ServiceCall) -> dict:
    """Handle read_file service call."""
    file_name = call.data[ATTR_FILE_NAME]
    file_encoding = call.data[ATTR_FILE_ENCODING].lower()

    if not call.hass.config.is_allowed_path(file_name):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_access_to_path",
            translation_placeholders={"filename": file_name},
        )

    if file_encoding not in ENCODING_LOADERS:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unsupported_file_encoding",
            translation_placeholders={
                "filename": file_name,
                "encoding": file_encoding,
            },
        )

    try:
        with open(file_name, encoding="utf-8") as file:
            file_content = file.read()
    except FileNotFoundError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="file_not_found",
            translation_placeholders={"filename": file_name},
        ) from err
    except OSError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="file_read_error",
            translation_placeholders={"filename": file_name},
        ) from err

    loader, error_type = ENCODING_LOADERS[file_encoding]
    try:
        data = loader(file_content)
    except error_type as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="file_decoding",
            translation_placeholders={"filename": file_name, "encoding": file_encoding},
        ) from err

    return {"data": data}

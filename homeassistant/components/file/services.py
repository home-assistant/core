"""File Service calls."""

from collections.abc import Callable
from enum import StrEnum
import json

import probatio
import yaml

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.os_error import os_read_error
from homeassistant.helpers.service import async_register_admin_service

from .const import DOMAIN


class FileService(StrEnum):
    """Store keys for File services."""

    READ_FILE = "read_file"


class FileServiceArgument(StrEnum):
    """Store keys for File service arguments."""

    FILE_NAME = "file_name"
    FILE_ENCODING = "file_encoding"


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register services for File integration."""

    async_register_admin_service(
        hass,
        DOMAIN,
        FileService.READ_FILE,
        read_file,
        schema=probatio.Schema(
            {
                probatio.Required(FileServiceArgument.FILE_NAME): cv.string,
                probatio.Required(FileServiceArgument.FILE_ENCODING): cv.string,
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
    file_name = call.data[FileServiceArgument.FILE_NAME]
    file_encoding = call.data[FileServiceArgument.FILE_ENCODING].lower()

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
    except OSError as err:
        raise os_read_error(err, file_name) from err

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

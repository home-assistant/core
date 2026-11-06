"""Services for the Minio integration."""

import probatio

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import ATTR_BUCKET, ATTR_KEY, DATA_MINIO, DOMAIN

ATTR_FILE_PATH = "file_path"

BUCKET_KEY_SCHEMA = probatio.Schema(
    {probatio.Required(ATTR_BUCKET): cv.string, probatio.Required(ATTR_KEY): cv.string}
)

BUCKET_KEY_FILE_SCHEMA = BUCKET_KEY_SCHEMA.extend(
    {probatio.Required(ATTR_FILE_PATH): cv.string}
)


def _put_file(call: ServiceCall) -> None:
    """Upload file service."""
    bucket = call.data[ATTR_BUCKET]
    key = call.data[ATTR_KEY]
    file_path = call.data[ATTR_FILE_PATH]

    if not call.hass.config.is_allowed_path(file_path):
        raise ValueError(f"Invalid file_path {file_path}")

    call.hass.data[DATA_MINIO].fput_object(bucket, key, file_path)


def _get_file(call: ServiceCall) -> None:
    """Download file service."""
    bucket = call.data[ATTR_BUCKET]
    key = call.data[ATTR_KEY]
    file_path = call.data[ATTR_FILE_PATH]

    if not call.hass.config.is_allowed_path(file_path):
        raise ValueError(f"Invalid file_path {file_path}")

    call.hass.data[DATA_MINIO].fget_object(bucket, key, file_path)


def _remove_file(call: ServiceCall) -> None:
    """Delete file service."""
    bucket = call.data[ATTR_BUCKET]
    key = call.data[ATTR_KEY]

    call.hass.data[DATA_MINIO].remove_object(bucket, key)


def setup_services(hass: HomeAssistant) -> None:
    """Register the Minio services."""
    hass.services.register(DOMAIN, "put", _put_file, schema=BUCKET_KEY_FILE_SCHEMA)
    hass.services.register(DOMAIN, "get", _get_file, schema=BUCKET_KEY_FILE_SCHEMA)
    hass.services.register(DOMAIN, "remove", _remove_file, schema=BUCKET_KEY_SCHEMA)

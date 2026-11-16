"""Services for the Minio integration."""

from enum import StrEnum

import probatio

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DATA_MINIO, DOMAIN


class MinioService(StrEnum):
    """Store keys for Minio services."""

    GET = "get"
    PUT = "put"
    REMOVE = "remove"


class MinioServiceArgument(StrEnum):
    """Store keys for Minio service arguments."""

    BUCKET = "bucket"
    KEY = "key"
    FILE_PATH = "file_path"


BUCKET_KEY_SCHEMA = probatio.Schema(
    {
        probatio.Required(MinioServiceArgument.BUCKET): cv.string,
        probatio.Required(MinioServiceArgument.KEY): cv.string,
    }
)

BUCKET_KEY_FILE_SCHEMA = BUCKET_KEY_SCHEMA.extend(
    {probatio.Required(MinioServiceArgument.FILE_PATH): cv.string}
)


def _put_file(call: ServiceCall) -> None:
    """Upload file service."""
    bucket = call.data[MinioServiceArgument.BUCKET]
    key = call.data[MinioServiceArgument.KEY]
    file_path = call.data[MinioServiceArgument.FILE_PATH]

    if not call.hass.config.is_allowed_path(file_path):
        raise ValueError(f"Invalid file_path {file_path}")

    call.hass.data[DATA_MINIO].fput_object(bucket, key, file_path)


def _get_file(call: ServiceCall) -> None:
    """Download file service."""
    bucket = call.data[MinioServiceArgument.BUCKET]
    key = call.data[MinioServiceArgument.KEY]
    file_path = call.data[MinioServiceArgument.FILE_PATH]

    if not call.hass.config.is_allowed_path(file_path):
        raise ValueError(f"Invalid file_path {file_path}")

    call.hass.data[DATA_MINIO].fget_object(bucket, key, file_path)


def _remove_file(call: ServiceCall) -> None:
    """Delete file service."""
    bucket = call.data[MinioServiceArgument.BUCKET]
    key = call.data[MinioServiceArgument.KEY]

    call.hass.data[DATA_MINIO].remove_object(bucket, key)


def setup_services(hass: HomeAssistant) -> None:
    """Register the Minio services."""
    hass.services.register(
        DOMAIN, MinioService.PUT, _put_file, schema=BUCKET_KEY_FILE_SCHEMA
    )
    hass.services.register(
        DOMAIN, MinioService.GET, _get_file, schema=BUCKET_KEY_FILE_SCHEMA
    )
    hass.services.register(
        DOMAIN, MinioService.REMOVE, _remove_file, schema=BUCKET_KEY_SCHEMA
    )

"""Constants for the Minio integration."""

from typing import TYPE_CHECKING

from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from minio import Minio

DOMAIN = "minio"

DATA_MINIO: HassKey[Minio] = HassKey(DOMAIN)

ATTR_BUCKET = "bucket"
ATTR_KEY = "key"

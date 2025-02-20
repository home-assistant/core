"""Constants for the S3 integration."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Final

from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "s3backup"

LOGGER = logging.getLogger(__package__)

SEPARATOR: Final = "#!#!#"

CONF_ACCESS_KEY: Final = "access_key"
CONF_SECRET_KEY: Final = "secret_key"
CONF_S3_URL: Final = "s3_url"
CONF_BUCKET: Final = "bucket"

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)

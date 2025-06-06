"""Constants for the Backblaze integration."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Final

from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "backblaze"

LOGGER = logging.getLogger(__package__)

SEPARATOR: Final = "#!#!#"

CONF_APPLICATION_KEY_ID: Final = "application_key_id"
CONF_APPLICATION_KEY: Final = "application_key"
CONF_BUCKET: Final = "bucket"

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)

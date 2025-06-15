"""Constants for the SFTP Backup Storage integration."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Final

from homeassistant.util.hass_dict import HassKey

DOMAIN: Final = "backup_sftp"

LOGGER = logging.getLogger(__package__)

CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_PRIVATE_KEY_FILE: Final = "private_key_file"
CONF_BACKUP_LOCATION: Final = "backup_location"

BUF_SIZE = 2**20 * 4  # 4MB

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)

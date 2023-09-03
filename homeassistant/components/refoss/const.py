"""const."""
from __future__ import annotations

from logging import Logger, getLogger
from typing import Final

LOGGER: Logger = getLogger(__package__)
DOMAIN: Final = "refoss"

REFOSS_DISCOVERY_NEW = "refoss_discovery_new"
REFOSS_HA_SIGNAL_UPDATE_ENTITY = "refoss_entry_update"

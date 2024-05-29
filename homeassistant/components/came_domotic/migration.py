# REVIEWED

"""Various helpers to handle config entry and api schema migrations."""

import logging

from homeassistant import core
from homeassistant.config_entries import ConfigEntry

LOGGER = logging.getLogger(__name__)


async def check_migration(hass: core.HomeAssistant, entry: ConfigEntry) -> None:
    """Check if config entry needs any migration actions."""

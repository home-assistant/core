"""The Model Context Protocol Server integration."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import http
from .const import DOMAIN
from .session import SessionManager
from .types import MCPServerConfigEntry

__all__ = [
    "CONFIG_SCHEMA",
    "DOMAIN",
    "async_setup",
    "async_setup_entry",
    "async_unload_entry",
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Model Context Protocol component."""
    http.async_register(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MCPServerConfigEntry) -> bool:
    """Set up Model Context Protocol Server from a config entry."""

    entry.runtime_data = SessionManager()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MCPServerConfigEntry) -> bool:
    """Unload a config entry."""
    session_manager = entry.runtime_data
    session_manager.close()
    return True

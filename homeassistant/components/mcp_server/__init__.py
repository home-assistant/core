"""The Model Context Protocol Server integration."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import http
from .const import CONF_REQUIRE_ADMIN, DOMAIN
from .session import SessionManager
from .types import MCPServerConfigEntry

__all__ = [
    "CONFIG_SCHEMA",
    "DOMAIN",
]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Model Context Protocol component."""
    http.async_register(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: MCPServerConfigEntry) -> bool:
    """Migrate a config entry."""
    if entry.version == 1 and entry.minor_version == 1:
        # 1.1 -> 1.2: Endpoints served before this option existed stay open.
        # A disabled config entry migrates only once enabled, so keep the
        # choice the options flow may have saved in the meantime.
        hass.config_entries.async_update_entry(
            entry,
            data={CONF_REQUIRE_ADMIN: False, **entry.data},
            minor_version=2,
        )

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

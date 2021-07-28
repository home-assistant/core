"""Config flow to configure Dynalite hub."""
from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.const import CONF_HOST

from .bridge import DynaliteBridge
from .const import DOMAIN, LOGGER
from .convert_config import convert_config


class DynaliteFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Dynalite config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the Dynalite flow."""
        self.host = None

    async def async_step_import(self, import_info: dict[str, Any]) -> Any:
        """Import a new bridge as a config entry."""
        LOGGER.debug("Starting async_step_import - %s", import_info)
        host = import_info[CONF_HOST]
        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == host:
                self.hass.config_entries.async_update_entry(
                    entry, data=dict(import_info)
                )
                return self.async_abort(reason="already_configured")

        # New entry
        bridge = DynaliteBridge(self.hass, convert_config(import_info))
        if not await bridge.async_setup():
            LOGGER.error("Unable to setup bridge - import info=%s", import_info)
            return self.async_abort(reason="no_connection")
        LOGGER.debug("Creating entry for the bridge - %s", import_info)
        return self.async_create_entry(title=host, data=import_info)

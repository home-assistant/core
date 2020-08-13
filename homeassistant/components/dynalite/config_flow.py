"""Config flow to configure Dynalite hub."""
from typing import Any, Dict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from .bridge import DynaliteBridge
from .const import DEFAULT_NAME, DEFAULT_PORT, DOMAIN, LOGGER


class DynaliteFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Dynalite config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize the Dynalite flow."""
        self.host = None

    def existing_host_entry(self, config) -> Any:
        """Check if a specific host is already configured and return its entry or None."""
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data[CONF_HOST] == config[CONF_HOST]:
                return entry
        return None

    async def check_bridge_connection(self, config) -> bool:
        """Check whether this bridge is available to connect."""
        bridge = DynaliteBridge(self.hass, config)
        if not await bridge.async_setup():
            LOGGER.error("Unable to setup bridge - config=%s", config)
            return False
        return True

    async def async_step_import(self, import_info: Dict[str, Any]) -> Any:
        """Import a new bridge as a config entry."""
        LOGGER.debug("Starting async_step_import - %s", import_info)
        host = import_info[CONF_HOST]
        entry = self.existing_host_entry(import_info)
        if entry:
            if entry.data != import_info:
                self.hass.config_entries.async_update_entry(entry, data=import_info)
            return self.async_abort(reason="already_configured")
        # New entry
        if not await self.check_bridge_connection(import_info):
            LOGGER.error("Unable to setup bridge - import info=%s", import_info)
            return self.async_abort(reason="no_connection")
        LOGGER.debug("Creating entry for the bridge - %s", import_info)
        return self.async_create_entry(title=host, data=import_info)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        # This is for backwards compatibility.
        return await self.async_step_init(user_input)

    async def async_step_init(self, user_input=None):
        """Handle a flow start."""
        if user_input is not None:
            # New entry
            if self.existing_host_entry(user_input):
                return self.async_abort(reason="already_configured")
            if not await self.check_bridge_connection(user_input):
                LOGGER.error("Unable to setup bridge - init user_input=%s", user_input)
                return self.async_abort(reason="no_connection")
            LOGGER.debug("Creating entry for the bridge - %s", user_input)
            return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                }
            ),
        )

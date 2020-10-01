"""Config flow to configure Dynalite hub."""
from typing import Any, Dict

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import callback

from .bridge import DynaliteBridge
from .const import DOMAIN, LOGGER


class DynaliteFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Dynalite config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize the Dynalite flow."""
        self.host = None

    async def async_step_import(self, import_info: Dict[str, Any]) -> Any:
        """Import a new bridge as a config entry."""
        LOGGER.debug("Starting async_step_import - %s", import_info)
        host = import_info[CONF_HOST]
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data[CONF_HOST] == host:
                if entry.data != import_info:
                    self.hass.config_entries.async_update_entry(entry, data=import_info)
                return self.async_abort(reason="already_configured")
        # New entry
        bridge = DynaliteBridge(self.hass, import_info)
        if not await bridge.async_setup():
            LOGGER.error("Unable to setup bridge - import info=%s", import_info)
            return self.async_abort(reason="no_connection")
        LOGGER.debug("Creating entry for the bridge - %s", import_info)
        return self.async_create_entry(title=host, data=import_info)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the Options Flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a option flow for the example."""

    def __init__(self, config_entry: config_entries.ConfigEntry):
        """Initialize options flow."""
        self.entry = config_entry
        self.options = config_entry.options

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "name",
                        description={"suggested_value": self.options.get("name")},
                    ): str,
                    vol.Optional(
                        "server",
                        description={"suggested_value": self.options.get("server")},
                    ): vol.Schema(
                        {
                            vol.Required("ip"): str,
                            vol.Optional("port"): int,
                            vol.Optional("advanced"): vol.Schema(
                                {
                                    vol.Optional("timeout"): int,
                                    vol.Optional("retries"): int,
                                }
                            ),
                        }
                    ),
                    vol.Required(
                        "protocol",
                        description={"suggested_value": self.options.get("protocol")},
                    ): vol.Schema(
                        {vol.Required("level"): int, vol.Optional("version"): str}
                    ),
                    vol.Optional(
                        "log", description={"suggested_value": self.options.get("log")}
                    ): str,
                }
            ),
        )

"""Config flow for TP-Link."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_DIMMER,
    CONF_DISCOVERY,
    CONF_LIGHT,
    CONF_RETRY_DELAY,
    CONF_RETRY_MAX_ATTEMPTS,
    CONF_STRIP,
    CONF_SWITCH,
    DEFAULT_DISCOVERY,
    DEFAULT_MAX_ATTEMPTS,
    DEFAULT_RETRY_DELAY,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LIGHT, default=""): str,
        vol.Optional(CONF_SWITCH, default=""): str,
        vol.Optional(CONF_DIMMER, default=""): str,
        vol.Optional(CONF_STRIP, default=""): str,
        vol.Optional(CONF_DISCOVERY, default=DEFAULT_DISCOVERY): bool,
        vol.Optional(CONF_RETRY_DELAY, default=DEFAULT_RETRY_DELAY): int,
        vol.Optional(CONF_RETRY_MAX_ATTEMPTS, default=DEFAULT_MAX_ATTEMPTS): int,
    }
)

_LOGGER = logging.getLogger(__name__)


class TplinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """TP-Link configuration flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return TpLinkOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Step when user initializes a integration."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if not user_input:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)
        return self.async_create_entry(title="", data=user_input)

    async def async_step_import(self, import_config):
        """Import a config entry from configuration.yaml."""
        return await self.async_step_user(import_config)


class TpLinkOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LIGHT,
                        default=self.config_entry.options.get(CONF_LIGHT, ""),
                    ): str,
                    vol.Optional(
                        CONF_SWITCH,
                        default=self.config_entry.options.get(CONF_SWITCH, ""),
                    ): str,
                    vol.Optional(
                        CONF_DIMMER,
                        default=self.config_entry.options.get(CONF_DIMMER, ""),
                    ): str,
                    vol.Optional(
                        CONF_STRIP,
                        default=self.config_entry.options.get(CONF_STRIP, ""),
                    ): str,
                    vol.Optional(
                        CONF_DISCOVERY,
                        default=self.config_entry.options.get(
                            CONF_DISCOVERY, DEFAULT_DISCOVERY
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_RETRY_DELAY,
                        default=self.config_entry.options.get(
                            CONF_RETRY_DELAY, DEFAULT_RETRY_DELAY
                        ),
                    ): int,
                    vol.Optional(
                        CONF_RETRY_MAX_ATTEMPTS,
                        default=self.config_entry.options.get(
                            CONF_RETRY_MAX_ATTEMPTS, DEFAULT_MAX_ATTEMPTS
                        ),
                    ): int,
                }
            ),
        )

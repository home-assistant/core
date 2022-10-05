"""PJLink config flow."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries, data_entry_flow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_ENCODING,
    DEFAULT_ENCODING,
    DEFAULT_PORT,
    DOMAIN,
    INTEGRATION_NAME,
)


class PJLinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """PJLink config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> data_entry_flow.FlowResult:
        """Create a user-configured PJLink device."""
        if user_input is not None:
            return self.async_create_entry(title=INTEGRATION_NAME, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): cv.string,
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): cv.port,
                    vol.Optional(CONF_NAME): cv.string,
                    vol.Optional(CONF_ENCODING, default=DEFAULT_ENCODING): cv.string,
                    vol.Optional(CONF_PASSWORD): cv.string,
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create an options flow."""
        return PJLinkOptionsFlowHandler(config_entry)


class PJLinkOptionsFlowHandler(config_entries.OptionsFlow):
    """PJLink options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title=INTEGRATION_NAME, data=user_input)

        options = self.config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=options.get(CONF_HOST)): cv.string,
                    vol.Optional(CONF_PORT, default=options.get(CONF_PORT)): cv.port,
                    vol.Optional(CONF_NAME, default=options.get(CONF_NAME)): cv.string,
                    vol.Optional(
                        CONF_ENCODING, default=options.get(CONF_ENCODING)
                    ): cv.string,
                    vol.Optional(
                        CONF_PASSWORD, default=options.get(CONF_PASSWORD)
                    ): cv.string,
                }
            ),
        )

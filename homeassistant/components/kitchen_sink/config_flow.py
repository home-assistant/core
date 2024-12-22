"""Config flow to configure the Kitchen Sink component."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from . import DOMAIN

CONF_BOOLEAN = "bool"
CONF_INT = "int"


class KitchenSinkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Kitchen Sink configuration flow."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler()

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Set the config entry up from yaml."""
        return self.async_create_entry(title="Kitchen Sink", data=import_data)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Reauth step."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Reauth confirm step."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return self.async_abort(reason="reauth_successful")


class OptionsFlowHandler(OptionsFlow):
    """Handle options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        return await self.async_step_options_1()

    async def async_step_options_1(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=self.config_entry.options | user_input)

        return self.async_show_form(
            step_id="options_1",
            data_schema=vol.Schema(
                {
                    vol.Required("section_1"): data_entry_flow.section(
                        vol.Schema(
                            {
                                vol.Optional(
                                    CONF_BOOLEAN,
                                    default=self.config_entry.options.get(
                                        CONF_BOOLEAN, False
                                    ),
                                ): bool,
                                vol.Optional(
                                    CONF_INT,
                                    default=self.config_entry.options.get(CONF_INT, 10),
                                ): int,
                            }
                        ),
                        {"collapsed": False},
                    ),
                }
            ),
        )

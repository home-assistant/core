"""The command_line config flow."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_NAME, CONF_PLATFORM, Platform
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_COMMAND_TIMEOUT, DOMAIN
from .schema import (
    CONF_JSON_ATTRIBUTES,
    DATA_SCHEMA_BINARY_SENSOR,
    DATA_SCHEMA_COMMON,
    DATA_SCHEMA_COVER,
    DATA_SCHEMA_NOTIFY,
    DATA_SCHEMA_SENSOR,
    DATA_SCHEMA_SWITCH,
)

PLATFORM_TO_DATA_SCHEMA = {
    Platform.SENSOR: DATA_SCHEMA_SENSOR,
    Platform.BINARY_SENSOR: DATA_SCHEMA_BINARY_SENSOR,
    Platform.COVER: DATA_SCHEMA_COVER,
    Platform.NOTIFY: DATA_SCHEMA_NOTIFY,
    Platform.SWITCH: DATA_SCHEMA_SWITCH,
}


class CommandLineConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Command Line."""

    VERSION = 1

    data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> CommandLineOptionsFlowHandler:
        """Get the options flow for this handler."""
        return CommandLineOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input:
            self.data = user_input
            return await self.async_step_final()

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA_COMMON,
            errors=errors,
        )

    async def async_step_final(self, user_input: dict[str, Any] = None) -> FlowResult:
        """Handle the configuration."""
        errors: dict[str, str] = {}

        if user_input:

            user_input[CONF_COMMAND_TIMEOUT] = int(user_input[CONF_COMMAND_TIMEOUT])

            name = (
                self.data[CONF_NAME]
                if self.data.get(CONF_NAME)
                else user_input[CONF_NAME]
            )

            return self.async_create_entry(
                title=name,
                data={},
                options={
                    **self.data,
                    **user_input,
                },
            )

        platform = self.data[CONF_PLATFORM]
        data_schema = PLATFORM_TO_DATA_SCHEMA[platform]
        return self.async_show_form(
            step_id="final",
            data_schema=data_schema,
            errors=errors,
        )


class CommandLineOptionsFlowHandler(OptionsFlow):
    """Handle a options flow for Command Line."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize Command Line options flow."""
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Command Line Options."""
        errors: dict[str, str] = {}

        if user_input:
            json_attr_list: list[str] | None = user_input.get(CONF_JSON_ATTRIBUTES)
            if json_attr_list in ([""], []):
                json_attr_list = None
                user_input[CONF_JSON_ATTRIBUTES] = json_attr_list
            user_input[CONF_COMMAND_TIMEOUT] = int(user_input[CONF_COMMAND_TIMEOUT])
            return self.async_create_entry(
                title="",
                data={
                    **self.entry.options,
                    **user_input,
                },
            )

        platform = self.entry.options[CONF_PLATFORM]
        schema = PLATFORM_TO_DATA_SCHEMA[platform].schema
        opt_data_schema = vol.Schema(
            {
                vol.Optional(
                    key.schema,
                    description={"suggested_value": self.entry.options.get(key.schema)},
                ): value
                for key, value in schema.items()
                if key.schema not in (CONF_NAME, CONF_PLATFORM)
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=opt_data_schema,
            errors=errors,
        )

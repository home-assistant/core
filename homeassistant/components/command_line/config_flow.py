"""The command_line config flow."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback

from homeassistant.const import (
    CONF_NAME,
    CONF_TYPE,
    CONF_UNIQUE_ID,
)
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
    DATA_SCHEMA_UNIQUE_ID,
)

TYPE_TO_DATA_SCHEMA = {
    "sensor": DATA_SCHEMA_SENSOR,
    "binary_sensor": DATA_SCHEMA_BINARY_SENSOR,
    "cover": DATA_SCHEMA_COVER,
    "notify": DATA_SCHEMA_NOTIFY,
    "switch": DATA_SCHEMA_SWITCH,
}


class CommandLineConfigFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Command Line."""

    VERSION = 1

    data: dict[str, Any] | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> CommandLineOptionsFlowHandler:
        """Get the options flow for this handler."""
        return CommandLineOptionsFlowHandler(config_entry)

    async def async_step_import(self, config: dict[str, Any] | None) -> FlowResult:
        """Import a configuration from config.yaml."""

        self._async_abort_entries_match(config)

        self.data = {CONF_NAME: config[CONF_NAME], CONF_TYPE: config[CONF_TYPE]}
        return await self.async_step_configure(user_input=config)

    async def async_step_user(self, user_input: dict[str, Any] = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input:
            self.data = user_input

            return self.async_step_configure()

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA_COMMON,
            errors=errors,
        )

    async def async_step_configure(
        self, user_input: dict[str, Any] = None
    ) -> FlowResult:
        """Handle the configuration."""
        errors: dict[str, str] = {}

        if user_input:

            if user_input[CONF_JSON_ATTRIBUTES] == [""]:
                user_input[CONF_JSON_ATTRIBUTES] = None
            user_input[CONF_COMMAND_TIMEOUT] = int(user_input[CONF_COMMAND_TIMEOUT])

            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={},
                options={
                    **self.data,
                    **user_input,
                },
            )

        data_schema = TYPE_TO_DATA_SCHEMA[user_input[CONF_TYPE]]
        return self.async_show_form(
            step_id="user",
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
            return self.async_create_entry(
                title="",
                data={
                    **self.entry.options,
                    **user_input,
                },
            )

        data_schema = TYPE_TO_DATA_SCHEMA[self.entry.options[CONF_TYPE]]
        data_schema_dict = {
            vol.Optional(
                key, description={"suggested_value": self.entry.options.get(key)}
            ): value
            for key, value in data_schema.__dict__.items()
        }
        opt_data_schema = vol.Schema(data_schema_dict)
        if self.entry.options.get(CONF_UNIQUE_ID):
            opt_data_schema.extend(DATA_SCHEMA_UNIQUE_ID)
        return self.async_show_form(
            step_id="init",
            data_schema=opt_data_schema,
            errors=errors,
        )

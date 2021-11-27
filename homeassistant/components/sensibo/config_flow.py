"""Adds config flow for Sensibo integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_ID, CONF_NAME
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN, ALL, DEFAULT_NAME


DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_ID, default=ALL): vol.All(cv.ensure_list, [cv.string]),
    }
)


class SensiboConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sensibo integration."""

    VERSION = 1

    entry: config_entries.ConfigEntry

    async def async_step_import(self, config: dict):
        """Import a configuration from config.yaml."""

        self.context.update(
            {"title_placeholders": {"Sensibo": f"YAML import {DOMAIN}"}}
        )
        return await self.async_step_user(user_input=config)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            api_key = user_input[CONF_API_KEY]
            name = user_input.get(CONF_NAME, DEFAULT_NAME)
            id_list = user_input[CONF_ID]

            await self.async_set_unique_id(name)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=name,
                data={
                    CONF_NAME: name,
                    CONF_API_KEY: api_key,
                    CONF_ID: id_list,
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA,
            errors=errors,
        )

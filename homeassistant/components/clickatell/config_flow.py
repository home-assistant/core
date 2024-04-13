"""Clickatell config flow."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_RECIPIENT
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_RECIPIENT): TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEL)
        ),
        vol.Required(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class ClickatellConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for imap."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        schema = CONFIG_SCHEMA

        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=schema)

        self._async_abort_entries_match(user_input)
        return self.async_create_entry(
            title=user_input[CONF_RECIPIENT], data=user_input
        )

    async def async_step_import(self, import_data: dict[str, str]) -> ConfigFlowResult:
        """Import entry from YAML."""
        api_key: str = import_data[CONF_API_KEY]
        recipient: str = import_data[CONF_RECIPIENT]
        name: str = import_data.get(CONF_NAME, recipient)
        data = {CONF_RECIPIENT: recipient, CONF_API_KEY: api_key}
        self._async_abort_entries_match(data)
        return self.async_create_entry(title=name, data=data)

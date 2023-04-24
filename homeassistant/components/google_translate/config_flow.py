"""Config flow for Google Translate Text-to-Speech integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.tts import CONF_LANG
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_TLD,
    DEFAULT_LANG,
    DEFAULT_TLD,
    DOMAIN,
    SUPPORT_LANGUAGES,
    SUPPORT_TLD,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LANG, default=DEFAULT_LANG): vol.In(SUPPORT_LANGUAGES),
        vol.Optional(CONF_TLD, default=DEFAULT_TLD): vol.In(SUPPORT_TLD),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Translate Text-to-Speech."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_LANG: user_input[CONF_LANG],
                    CONF_TLD: user_input[CONF_TLD],
                }
            )
            return self.async_create_entry(
                title="Google Translate Text-to-Speech", data=user_input
            )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

    async def async_step_import(self, data: dict[str, Any]) -> FlowResult:
        """Handle the import step."""
        return await self.async_step_user(user_input=data)

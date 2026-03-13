"""Config flow for the Cloud integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.helpers import llm
from homeassistant.helpers.selector import TemplateSelector

from .const import CONF_PROMPT, DOMAIN


class CloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the Cloud integration."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return CloudOptionsFlow(config_entry)

    async def async_step_system(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the system step."""
        return self.async_create_entry(title="Home Assistant Cloud", data={})


class CloudOptionsFlow(OptionsFlow):
    """Handle Home Assistant Cloud options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Cloud options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PROMPT,
                        description={
                            "suggested_value": self._config_entry.options.get(
                                CONF_PROMPT, llm.DEFAULT_INSTRUCTIONS_PROMPT
                            )
                        },
                    ): TemplateSelector(),
                }
            ),
        )

"""Options flow for the NeoPool integration."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload

from .const import CONF_USE_LIGHT


class NeoPoolOptionsFlowHandler(OptionsFlowWithReload):
    """Handle options flow for NeoPool integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step of the options flow."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_USE_LIGHT,
                    default=options.get(CONF_USE_LIGHT, False),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

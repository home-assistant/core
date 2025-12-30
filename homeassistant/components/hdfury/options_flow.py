"""Options flow for HDFury Integration."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithReload

from .const import OPTION_INPUT_LABELS


class HDFuryOptionsFlow(OptionsFlowWithReload):
    """Handle Options Flow for HDFury."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle Options."""

        if user_input is not None:
            return self.async_create_entry(title="", data={"option_labels": user_input})

        current_labels = self.config_entry.options.get("option_labels", {})
        schema = vol.Schema(
            {
                vol.Optional(opt, default=current_labels.get(opt, label)): str
                for opt, label in OPTION_INPUT_LABELS.items()
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            description_placeholders={"entity": self.config_entry.title},
        )

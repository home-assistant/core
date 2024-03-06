"""Config flow for aWATTar integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers.selector import selector

from .const import CONF_COUNTRY, DOMAIN

data_schema = {
    vol.Required(CONF_COUNTRY): selector(
        {
            "select": {
                "options": ["Austria", "Germany"],
            }
        }
    ),
}


class AwattarFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for aWATTar integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema(data_schema)
            )

        return self.async_create_entry(
            title="aWATTar",
            data={
                CONF_COUNTRY: user_input[CONF_COUNTRY],
            },
        )

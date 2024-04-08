"""Config flow for aWATTar integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_COUNTRY_CODE

from .const import DOMAIN

COUNTRY_CODES = ["AT", "DE"]


class AwattarFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for aWATTar integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""

        await self.async_set_unique_id(DOMAIN)

        if user_input is not None:
            return self.async_create_entry(
                title="aWATTar",
                data=user_input,
            )

        user_schema = vol.Schema(
            {
                vol.Required(CONF_COUNTRY_CODE, default=COUNTRY_CODES[0]): vol.In(
                    COUNTRY_CODES
                ),
            }
        )

        return self.async_show_form(step_id="user", data_schema=user_schema)

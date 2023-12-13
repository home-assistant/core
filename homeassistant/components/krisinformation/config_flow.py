"""Config flow for krisinformation integration."""
from __future__ import annotations

# Importing necessary modules and classes.
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

# Importing custom constants and exceptions from the integration.
from .const import CONF_COUNTY, COUNTY_CODES, DEFAULT_NAME, DOMAIN

# Defining the user data schema for the configuration step.
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Required(CONF_COUNTY): SelectSelector(
            SelectSelectorConfig(
                options=sorted(COUNTY_CODES.values()),
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_COUNTY,
            )
        ),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for krisinformation."""

    VERSION = 1

    # Step to handle user input during configuration
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            info = {"title": user_input[CONF_NAME]}
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

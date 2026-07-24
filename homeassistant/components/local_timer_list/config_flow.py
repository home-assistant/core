"""Config flow for the Local Timer list integration."""

from typing import Any, override

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import CONF_TIMER_LIST_NAME, DOMAIN

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TIMER_LIST_NAME): str,
    }
)


class LocalTimerListConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Local Timer list."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_TIMER_LIST_NAME], data=user_input
            )

        return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

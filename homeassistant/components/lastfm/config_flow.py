"""Config flow for LastFm."""
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.typing import ConfigType

from .const import CONF_USERS, DOMAIN


class LastFmFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow handler for LastFm."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Initialize user input."""
        if user_input is not None:
            return self.async_create_entry(title="LastFM", data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                    vol.Required(CONF_USERS): list[str],
                }
            ),
        )

    async def async_step_import(self, import_config: ConfigType) -> FlowResult:
        """Import config from yaml."""
        for entry in self._async_current_entries():
            if entry.data[CONF_API_KEY] == import_config[CONF_API_KEY]:
                return self.async_abort(reason="already_configured")
        return await self.async_step_user(import_config)

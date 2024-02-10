"""Config flow for Opnsense integration."""
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_VERIFY_SSL
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_API_SECRET, CONF_TRACKER_INTERFACE, DOMAIN


class OPNSenseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """OPNSense config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual initiation of the config flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST): str,
                        vol.Required(CONF_API_KEY): str,
                        vol.Required(CONF_API_SECRET): str,
                        vol.Optional(CONF_VERIFY_SSL, default=False): bool,
                        vol.Optional(
                            CONF_TRACKER_INTERFACE, default=[]
                        ): SelectSelector(
                            SelectSelectorConfig(
                                options=[],
                                multiple=True,
                                custom_value=True,
                                mode=SelectSelectorMode.DROPDOWN,
                            )
                        ),
                    }
                ),
            )

        self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
        return self.async_create_entry(
            title=user_input[CONF_HOST],
            data={},
            options={**user_input},
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> FlowResult:
        """Import OPNSense config from configuration.yaml."""
        return await self.async_step_user(user_input=import_info)

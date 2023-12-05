"""Config flow for Opnsense integration."""
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_URL,
    CONF_VERIFY_SSL,
)
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_API_SECRET,
    CONF_TRACKER_INTERFACE,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)


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
                        vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                        vol.Required(CONF_URL): str,
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

        self._async_abort_entries_match({CONF_NAME: user_input[CONF_NAME]})
        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data={},
            options={**user_input},
        )

    async def async_step_import(self, import_info: dict[str, Any]) -> FlowResult:
        """Import OPNSense config from configuration.yaml."""
        return await self.async_step_user(user_input=import_info)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """OPNSense options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): cv.positive_int,
                    vol.Required(
                        CONF_TIMEOUT,
                        default=self.config_entry.options.get(
                            CONF_TIMEOUT, DEFAULT_TIMEOUT
                        ),
                    ): cv.positive_int,
                    vol.Optional(
                        CONF_TRACKER_INTERFACE,
                        default=self.config_entry.options.get(CONF_TRACKER_INTERFACE),
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

"""Signal Messenger config flow."""

from __future__ import annotations

from pysignalclirestapi import SignalCliRestApi
import requests
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import (
    CONF_RECP_NR,
    CONF_SENDER_NR,
    CONF_SIGNAL_CLI_REST_API,
    DEFAULT_HOST,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="signal"): selector.TextSelector(),
        vol.Required(
            CONF_SIGNAL_CLI_REST_API, default=DEFAULT_HOST
        ): selector.TextSelector(),
        vol.Required(CONF_SENDER_NR): selector.TextSelector(),
        vol.Required(CONF_RECP_NR): selector.TextSelector(),
    }
)


class SignalMessengerFlowHandler(ConfigFlow, domain=DOMAIN):
    """Signal Messenger config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors = {}
        if user_input is not None:
            try:
                signal_cli_rest_api = SignalCliRestApi(
                    user_input[CONF_SIGNAL_CLI_REST_API], user_input[CONF_SENDER_NR]
                )
                signal_cli_rest_api_about = await self.hass.async_add_executor_job(
                    signal_cli_rest_api.about
                )
            except requests.ConnectionError:
                signal_cli_rest_api_about = None

            if signal_cli_rest_api_about is None:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Signal {user_input[CONF_NAME]}",
                    data={
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_SIGNAL_CLI_REST_API: user_input[CONF_SIGNAL_CLI_REST_API],
                        CONF_SENDER_NR: user_input[CONF_SENDER_NR],
                        CONF_RECP_NR: user_input[CONF_RECP_NR].split(" "),
                    },
                )

        data_schema = self.add_suggested_values_to_schema(DATA_SCHEMA, user_input)
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

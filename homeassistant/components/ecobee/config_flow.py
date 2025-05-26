"""Config flow to configure ecobee."""

from typing import Any

from pyecobee import ECOBEE_API_KEY, Ecobee
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY

from .const import CONF_REFRESH_TOKEN, DOMAIN

_USER_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})


class EcobeeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an ecobee config flow."""

    VERSION = 1

    _ecobee: Ecobee

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            # Use the user-supplied API key to attempt to obtain a PIN from ecobee.
            self._ecobee = Ecobee(config={ECOBEE_API_KEY: user_input[CONF_API_KEY]})

            if await self.hass.async_add_executor_job(self._ecobee.request_pin):
                # We have a PIN; move to the next step of the flow.
                return await self.async_step_authorize()
            errors["base"] = "pin_request_failed"

        return self.async_show_form(
            step_id="user",
            data_schema=_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Present the user with the PIN so that the app can be authorized on ecobee.com."""
        errors = {}

        if user_input is not None:
            # Attempt to obtain tokens from ecobee and finish the flow.
            if await self.hass.async_add_executor_job(self._ecobee.request_tokens):
                # Refresh token obtained; create the config entry.
                config = {
                    CONF_API_KEY: self._ecobee.api_key,
                    CONF_REFRESH_TOKEN: self._ecobee.refresh_token,
                }
                return self.async_create_entry(title=DOMAIN, data=config)
            errors["base"] = "token_request_failed"

        return self.async_show_form(
            step_id="authorize",
            errors=errors,
            description_placeholders={"pin": self._ecobee.pin},
        )

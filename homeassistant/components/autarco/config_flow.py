"""Config flow for Autarco integration."""

from __future__ import annotations

from typing import Any

from autarco import Autarco, AutarcoAuthenticationError, AutarcoConnectionError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class AutarcoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Autarco."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match({CONF_EMAIL: user_input[CONF_EMAIL]})
            client = Autarco(
                email=user_input[CONF_EMAIL],
                password=user_input[CONF_PASSWORD],
                session=async_get_clientsession(self.hass),
            )
            try:
                await client.get_account()
            except AutarcoAuthenticationError:
                errors["base"] = "invalid_auth"
            except AutarcoConnectionError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL],
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
        return self.async_show_form(
            step_id="user",
            errors=errors,
            data_schema=DATA_SCHEMA,
        )

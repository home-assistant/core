"""Config flow for the Nintendo Switch Parental Controls integration."""

from __future__ import annotations

import logging
from typing import Any

from pynintendoparental import Authenticator
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import CONF_SESSION_TOKEN, CONF_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_CONFIGURE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_UPDATE_INTERVAL, default=60): selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=30,
                step=1,
                unit_of_measurement="s",
                mode=selector.NumberSelectorMode.BOX,
            )
        )
    }
)


class NintendoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nintendo Switch Parental Controls."""

    def __init__(self) -> None:
        """Initialize a new config flow instance."""
        self.auth = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if not user_input:
            self.auth = Authenticator.generate_login()
            return await self.async_step_nintendo_website_auth()
        return self.async_show_form(step_id="user")

    async def async_step_nintendo_website_auth(
        self, user_input=None
    ) -> ConfigFlowResult:
        """Begin authentication flow with Nintendo website."""
        if user_input is not None:
            await self.auth.complete_login(self.auth, user_input[CONF_API_TOKEN], False)
            return await ()
        return self.async_show_form(
            step_id="nintendo_website_auth",
            description_placeholders={"link": self.auth.login_url},
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
        )

    async def async_step_configure(self, user_input=None) -> ConfigFlowResult:
        """Configure the update interval and create config entry."""
        if user_input is not None:
            assert self.auth.account_id
            return self.async_create_entry(
                title=self.auth.account_id,
                data={
                    CONF_SESSION_TOKEN: self.auth.get_session_token,
                    CONF_UPDATE_INTERVAL: user_input[CONF_UPDATE_INTERVAL],
                },
            )
        return self.async_show_form(
            step_id="configure", data_schema=STEP_CONFIGURE_DATA_SCHEMA
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

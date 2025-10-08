"""Config flow for the Nintendo Switch Parental Controls integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from pynintendoparental import Authenticator
from pynintendoparental.exceptions import HttpException, InvalidSessionTokenException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_SESSION_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NintendoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nintendo Switch Parental Controls."""

    def __init__(self) -> None:
        """Initialize a new config flow instance."""
        self.auth: Authenticator | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if self.auth is None:
            self.auth = Authenticator.generate_login(
                client_session=async_get_clientsession(self.hass)
            )

        if user_input is not None:
            try:
                await self.auth.complete_login(
                    self.auth, user_input[CONF_API_TOKEN], False
                )
            except (ValueError, InvalidSessionTokenException, HttpException):
                errors["base"] = "invalid_auth"
            else:
                if TYPE_CHECKING:
                    assert self.auth.account_id
                await self.async_set_unique_id(self.auth.account_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=self.auth.account_id,
                    data={
                        CONF_SESSION_TOKEN: self.auth.get_session_token,
                    },
                )
        return self.async_show_form(
            step_id="user",
            description_placeholders={"link": self.auth.login_url},
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            errors=errors,
        )

    async def async_step_reauth(
        self, user_input: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauthentication on an API error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauth dialog."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if self.auth is None:
            self.auth = Authenticator.generate_login(
                client_session=async_get_clientsession(self.hass)
            )
        if user_input is not None:
            try:
                await self.auth.complete_login(
                    self.auth, user_input[CONF_API_TOKEN], False
                )
            except (ValueError, InvalidSessionTokenException, HttpException):
                errors["base"] = "invalid_auth"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={**reauth_entry.data,
                        CONF_SESSION_TOKEN: self.auth.get_session_token,
                    },
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"link": self.auth.login_url},
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            errors=errors,
        )

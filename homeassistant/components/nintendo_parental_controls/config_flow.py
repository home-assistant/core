"""Config flow for the Nintendo Switch parental controls integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import TYPE_CHECKING, Any

from pynintendoauth.exceptions import HttpException, InvalidSessionTokenException
from pynintendoparental import Authenticator
from pynintendoparental.api import Api
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import APP_SETUP_URL, CONF_SESSION_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)


class NintendoConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nintendo Switch parental controls."""

    def __init__(self) -> None:
        """Initialize a new config flow instance."""
        self.auth: Authenticator | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors = {}
        if self.auth is None:
            self.auth = Authenticator(client_session=async_get_clientsession(self.hass))

        if user_input is not None:
            nintendo_api = Api(
                self.auth, self.hass.config.time_zone, self.hass.config.language
            )
            try:
                await self.auth.async_complete_login(user_input[CONF_API_TOKEN])
            except (ValueError, InvalidSessionTokenException, HttpException):
                errors["base"] = "invalid_auth"
            else:
                if TYPE_CHECKING:
                    assert self.auth.account_id
                await self.async_set_unique_id(self.auth.account_id)
                self._abort_if_unique_id_configured()
            try:
                if "base" not in errors:
                    await nintendo_api.async_get_account_devices()
            except HttpException as err:
                if err.status_code == 404:
                    return self.async_abort(
                        reason="no_devices_found",
                        description_placeholders={"more_info_url": APP_SETUP_URL},
                    )
                errors["base"] = "cannot_connect"
            else:
                if "base" not in errors:
                    return self.async_create_entry(
                        title=self.auth.account_id,
                        data={
                            CONF_SESSION_TOKEN: self.auth.session_token,
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
            self.auth = Authenticator(client_session=async_get_clientsession(self.hass))
        if user_input is not None:
            try:
                await self.auth.async_complete_login(user_input[CONF_API_TOKEN])
            except (ValueError, InvalidSessionTokenException, HttpException):
                errors["base"] = "invalid_auth"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        **reauth_entry.data,
                        CONF_SESSION_TOKEN: self.auth.session_token,
                    },
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            description_placeholders={"link": self.auth.login_url},
            data_schema=vol.Schema({vol.Required(CONF_API_TOKEN): str}),
            errors=errors,
        )

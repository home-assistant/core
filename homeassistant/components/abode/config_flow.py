"""Config flow for the Abode Security System component."""

from __future__ import annotations

from collections.abc import Mapping
from http import HTTPStatus
from typing import Any, cast

from jaraco.abode.client import Client as Abode
from jaraco.abode.exceptions import (
    AuthenticationException as AbodeAuthenticationException,
    Exception as AbodeException,
)
from jaraco.abode.helpers.errors import MFA_CODE_REQUIRED
from requests.exceptions import ConnectTimeout, HTTPError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_POLLING, DOMAIN, LOGGER

CONF_MFA = "mfa_code"


class AbodeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for Abode."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self.data_schema = {
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        }
        self.mfa_data_schema = {
            vol.Required(CONF_MFA): str,
        }

        self._mfa_code: str | None = None
        self._password: str | None = None
        self._polling: bool = False
        self._username: str | None = None

    async def _async_abode_login(self, step_id: str) -> ConfigFlowResult:
        """Handle login with Abode."""
        errors = {}

        try:
            await self.hass.async_add_executor_job(
                Abode, self._username, self._password, True, False, False
            )

        except AbodeException as ex:
            if ex.errcode == MFA_CODE_REQUIRED[0]:
                return await self.async_step_mfa()

            LOGGER.error("Unable to connect to Abode: %s", ex)

            if ex.errcode == HTTPStatus.BAD_REQUEST:
                errors = {"base": "invalid_auth"}

            else:
                errors = {"base": "cannot_connect"}

        except (ConnectTimeout, HTTPError):
            errors = {"base": "cannot_connect"}

        if errors:
            return self.async_show_form(
                step_id=step_id, data_schema=vol.Schema(self.data_schema), errors=errors
            )

        return await self._async_create_entry()

    async def _async_abode_mfa_login(self) -> ConfigFlowResult:
        """Handle multi-factor authentication (MFA) login with Abode."""
        try:
            # Create instance to access login method for passing MFA code
            abode = Abode(auto_login=False, get_devices=False, get_automations=False)
            await self.hass.async_add_executor_job(
                abode.login, self._username, self._password, self._mfa_code
            )

        except AbodeAuthenticationException:
            return self.async_show_form(
                step_id="mfa",
                data_schema=vol.Schema(self.mfa_data_schema),
                errors={"base": "invalid_mfa_code"},
            )

        return await self._async_create_entry()

    async def _async_create_entry(self) -> ConfigFlowResult:
        """Create the config entry."""
        config_data = {
            CONF_USERNAME: self._username,
            CONF_PASSWORD: self._password,
            CONF_POLLING: self._polling,
        }
        existing_entry = await self.async_set_unique_id(self._username)

        if existing_entry:
            return self.async_update_reload_and_abort(existing_entry, data=config_data)

        return self.async_create_entry(
            title=cast(str, self._username), data=config_data
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema(self.data_schema)
            )

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        return await self._async_abode_login(step_id="user")

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a multi-factor authentication (MFA) flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="mfa", data_schema=vol.Schema(self.mfa_data_schema)
            )

        self._mfa_code = user_input[CONF_MFA]

        return await self._async_abode_mfa_login()

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthorization request from Abode."""
        self._username = entry_data[CONF_USERNAME]

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reauthorization flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_USERNAME, default=self._username): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
            )

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]

        return await self._async_abode_login(step_id="reauth_confirm")

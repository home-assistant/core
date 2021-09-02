"""Config flow to configure the SimpliSafe component."""
from __future__ import annotations

from typing import Any

from simplipy import get_api
from simplipy.api import API
from simplipy.errors import (
    InvalidCredentialsError,
    PendingAuthorizationError,
    SimplipyError,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.typing import ConfigType

from . import async_get_client_id
from .const import DOMAIN, LOGGER

FULL_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_CODE): str,
    }
)
PASSWORD_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class SimpliSafeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a SimpliSafe config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._code: str | None = None
        self._password: str | None = None
        self._username: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SimpliSafeOptionsFlowHandler:
        """Define the config flow to handle options."""
        return SimpliSafeOptionsFlowHandler(config_entry)

    async def _async_get_simplisafe_api(self) -> API:
        """Get an authenticated SimpliSafe API client."""
        assert self._username
        assert self._password

        client_id = await async_get_client_id(self.hass)
        websession = aiohttp_client.async_get_clientsession(self.hass)

        return await get_api(
            self._username,
            self._password,
            client_id=client_id,
            session=websession,
        )

    async def _async_login_during_step(
        self, *, step_id: str, form_schema: vol.Schema
    ) -> FlowResult:
        """Attempt to log into the API from within a config flow step."""
        errors = {}

        try:
            await self._async_get_simplisafe_api()
        except PendingAuthorizationError:
            LOGGER.info("Awaiting confirmation of MFA email click")
            return await self.async_step_mfa()
        except InvalidCredentialsError:
            errors = {"base": "invalid_auth"}
        except SimplipyError as err:
            LOGGER.error("Unknown error while logging into SimpliSafe: %s", err)
            errors = {"base": "unknown"}

        if errors:
            return self.async_show_form(
                step_id=step_id,
                data_schema=form_schema,
                errors=errors,
            )

        return await self.async_step_finish(
            {
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_CODE: self._code,
            }
        )

    async def async_step_finish(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle finish config entry setup."""
        assert self._username

        existing_entry = await self.async_set_unique_id(self._username)
        if existing_entry:
            self.hass.config_entries.async_update_entry(existing_entry, data=user_input)
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )
            return self.async_abort(reason="reauth_successful")
        return self.async_create_entry(title=self._username, data=user_input)

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle multi-factor auth confirmation."""
        if user_input is None:
            return self.async_show_form(step_id="mfa")

        try:
            await self._async_get_simplisafe_api()
        except PendingAuthorizationError:
            LOGGER.error("Still awaiting confirmation of MFA email click")
            return self.async_show_form(
                step_id="mfa", errors={"base": "still_awaiting_mfa"}
            )

        return await self.async_step_finish(
            {
                CONF_USERNAME: self._username,
                CONF_PASSWORD: self._password,
                CONF_CODE: self._code,
            }
        )

    async def async_step_reauth(self, config: ConfigType) -> FlowResult:
        """Handle configuration by re-auth."""
        self._code = config.get(CONF_CODE)
        self._username = config[CONF_USERNAME]

        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-auth completion."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm", data_schema=PASSWORD_DATA_SCHEMA
            )

        self._password = user_input[CONF_PASSWORD]

        return await self._async_login_during_step(
            step_id="reauth_confirm", form_schema=PASSWORD_DATA_SCHEMA
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        if not user_input:
            return self.async_show_form(step_id="user", data_schema=FULL_DATA_SCHEMA)

        await self.async_set_unique_id(user_input[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        self._code = user_input.get(CONF_CODE)
        self._password = user_input[CONF_PASSWORD]
        self._username = user_input[CONF_USERNAME]

        return await self._async_login_during_step(
            step_id="user", form_schema=FULL_DATA_SCHEMA
        )


class SimpliSafeOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle a SimpliSafe options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize."""
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
                    vol.Optional(
                        CONF_CODE,
                        description={
                            "suggested_value": self.config_entry.options.get(CONF_CODE)
                        },
                    ): str
                }
            ),
        )

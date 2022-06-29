"""Config flow to configure the SimpliSafe component."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import async_timeout
from simplipy import API
from simplipy.api import AuthStates
from simplipy.errors import InvalidCredentialsError, SimplipyError, Verify2FAPending
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import DOMAIN, LOGGER

DEFAULT_EMAIL_2FA_SLEEP = 3
DEFAULT_EMAIL_2FA_TIMEOUT = 600

STEP_REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): cv.string,
    }
)

STEP_SMS_2FA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CODE): cv.string,
    }
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class SimpliSafeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a SimpliSafe config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._email_2fa_task: asyncio.Task | None = None
        self._password: str | None = None
        self._reauth: bool = False
        self._simplisafe: API | None = None
        self._username: str | None = None

    async def _async_authenticate(
        self, originating_step_id: str, originating_step_schema: vol.Schema
    ) -> FlowResult:
        """Attempt to authenticate to the SimpliSafe API."""
        assert self._password
        assert self._username

        errors = {}
        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            self._simplisafe = await API.async_from_credentials(
                self._username, self._password, session=session
            )
        except InvalidCredentialsError:
            errors = {"base": "invalid_auth"}
        except SimplipyError as err:
            LOGGER.error("Unknown error while logging into SimpliSafe: %s", err)
            errors = {"base": "unknown"}

        if errors:
            return self.async_show_form(
                step_id=originating_step_id,
                data_schema=originating_step_schema,
                errors=errors,
                description_placeholders={CONF_USERNAME: self._username},
            )

        assert self._simplisafe

        if self._simplisafe.auth_state == AuthStates.PENDING_2FA_SMS:
            return await self.async_step_sms_2fa()
        return await self.async_step_email_2fa()

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SimpliSafeOptionsFlowHandler:
        """Define the config flow to handle options."""
        return SimpliSafeOptionsFlowHandler(config_entry)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        self._reauth = True

        if CONF_USERNAME not in entry_data:
            # Old versions of the config flow may not have the username by this point;
            # in that case, we reauth them by making them go through the user flow:
            return await self.async_step_user()

        self._username = entry_data[CONF_USERNAME]
        return await self.async_step_reauth_confirm()

    async def _async_get_email_2fa(self) -> None:
        """Define a task to wait for email-based 2FA."""
        assert self._simplisafe

        try:
            async with async_timeout.timeout(DEFAULT_EMAIL_2FA_TIMEOUT):
                while True:
                    try:
                        await self._simplisafe.async_verify_2fa_email()
                    except Verify2FAPending:
                        LOGGER.info("Email-based 2FA pending; trying again")
                        await asyncio.sleep(DEFAULT_EMAIL_2FA_SLEEP)
                    else:
                        break
        finally:
            self.hass.async_create_task(
                self.hass.config_entries.flow.async_configure(flow_id=self.flow_id)
            )

    async def async_step_email_2fa(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle email-based two-factor authentication."""
        if not self._email_2fa_task:
            self._email_2fa_task = self.hass.async_create_task(
                self._async_get_email_2fa()
            )
            return self.async_show_progress(
                step_id="email_2fa", progress_action="email_2fa"
            )

        try:
            await self._email_2fa_task
        except asyncio.TimeoutError:
            return self.async_show_progress_done(next_step_id="email_2fa_error")
        return self.async_show_progress_done(next_step_id="finish")

    async def async_step_email_2fa_error(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle an error during email-based two-factor authentication."""
        return self.async_abort(reason="email_2fa_timed_out")

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the final step."""
        assert self._simplisafe
        assert self._username

        data = {
            CONF_USERNAME: self._username,
            CONF_TOKEN: self._simplisafe.refresh_token,
        }

        user_id = str(self._simplisafe.user_id)

        if self._reauth:
            # "Old" config entries utilized the user's email address (username) as the
            # unique ID, whereas "new" config entries utilize the SimpliSafe user ID –
            # only one can exist at a time, but the presence of either one is a
            # candidate for re-auth:
            if existing_entries := [
                entry
                for entry in self.hass.config_entries.async_entries()
                if entry.domain == DOMAIN
                and entry.unique_id in (self._username, user_id)
            ]:
                existing_entry = existing_entries[0]
                self.hass.config_entries.async_update_entry(
                    existing_entry, unique_id=user_id, title=self._username, data=data
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(existing_entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")

        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=self._username, data=data)

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle re-auth completion."""
        if not user_input:
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=STEP_REAUTH_SCHEMA,
                description_placeholders={CONF_USERNAME: self._username},
            )

        self._password = user_input[CONF_PASSWORD]
        return await self._async_authenticate("reauth_confirm", STEP_REAUTH_SCHEMA)

    async def async_step_sms_2fa(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle SMS-based two-factor authentication."""
        if not user_input:
            return self.async_show_form(
                step_id="sms_2fa",
                data_schema=STEP_SMS_2FA_SCHEMA,
            )

        assert self._simplisafe

        try:
            await self._simplisafe.async_verify_2fa_sms(user_input[CONF_CODE])
        except InvalidCredentialsError:
            return self.async_show_form(
                step_id="sms_2fa",
                data_schema=STEP_SMS_2FA_SCHEMA,
                errors={CONF_CODE: "invalid_auth"},
            )

        return await self.async_step_finish()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_SCHEMA)

        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]
        return await self._async_authenticate("user", STEP_USER_SCHEMA)


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

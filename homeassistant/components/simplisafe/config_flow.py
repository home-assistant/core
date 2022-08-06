"""Config flow to configure the SimpliSafe component."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any, NamedTuple

from simplipy import API
from simplipy.errors import InvalidCredentialsError, SimplipyError
from simplipy.util.auth import (
    get_auth0_code_challenge,
    get_auth0_code_verifier,
    get_auth_url,
)
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CODE, CONF_TOKEN, CONF_URL, CONF_USERNAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import aiohttp_client, config_validation as cv

from .const import DOMAIN, LOGGER

CONF_AUTH_CODE = "auth_code"

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AUTH_CODE): cv.string,
    }
)


class SimpliSafeOAuthValues(NamedTuple):
    """Define a named tuple to handle SimpliSafe OAuth strings."""

    auth_url: str
    code_verifier: str


@callback
def async_get_simplisafe_oauth_values() -> SimpliSafeOAuthValues:
    """Get a SimpliSafe OAuth code verifier and auth URL."""
    code_verifier = get_auth0_code_verifier()
    code_challenge = get_auth0_code_challenge(code_verifier)
    auth_url = get_auth_url(code_challenge)
    return SimpliSafeOAuthValues(auth_url, code_verifier)


class SimpliSafeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a SimpliSafe config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._oauth_values: SimpliSafeOAuthValues = async_get_simplisafe_oauth_values()
        self._reauth: bool = False

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SimpliSafeOptionsFlowHandler:
        """Define the config flow to handle options."""
        return SimpliSafeOptionsFlowHandler(config_entry)

    async def async_step_reauth(self, config: Mapping[str, Any]) -> FlowResult:
        """Handle configuration by re-auth."""
        self._reauth = True
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_SCHEMA,
                description_placeholders={CONF_URL: self._oauth_values.auth_url},
            )

        auth_code = user_input[CONF_AUTH_CODE]

        if auth_code.startswith("="):
            # Sometimes, users may include the "=" from the URL query param; in that
            # case, strip it off and proceed:
            LOGGER.debug('Stripping "=" from the start of the authorization code')
            auth_code = auth_code[1:]

        if len(auth_code) != 45:
            # SimpliSafe authorization codes are 45 characters in length; if the user
            # provides something different, stop them here:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_SCHEMA,
                errors={CONF_AUTH_CODE: "invalid_auth_code_length"},
                description_placeholders={CONF_URL: self._oauth_values.auth_url},
            )

        errors = {}
        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            simplisafe = await API.async_from_auth(
                auth_code,
                self._oauth_values.code_verifier,
                session=session,
            )
        except InvalidCredentialsError:
            errors = {CONF_AUTH_CODE: "invalid_auth"}
        except SimplipyError as err:
            LOGGER.error("Unknown error while logging into SimpliSafe: %s", err)
            errors = {"base": "unknown"}

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_SCHEMA,
                errors=errors,
                description_placeholders={CONF_URL: self._oauth_values.auth_url},
            )

        simplisafe_user_id = str(simplisafe.user_id)
        data = {CONF_USERNAME: simplisafe_user_id, CONF_TOKEN: simplisafe.refresh_token}

        if self._reauth:
            existing_entry = await self.async_set_unique_id(simplisafe_user_id)
            if not existing_entry:
                # If we don't have an entry that matches this user ID, the user logged
                # in with different credentials:
                return self.async_abort(reason="wrong_account")

            self.hass.config_entries.async_update_entry(
                existing_entry, unique_id=simplisafe_user_id, data=data
            )
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(existing_entry.entry_id)
            )
            return self.async_abort(reason="reauth_successful")

        await self.async_set_unique_id(simplisafe_user_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=simplisafe_user_id, data=data)


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

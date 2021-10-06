"""Config flow to configure the SimpliSafe component."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, NamedTuple

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
from homeassistant.helpers.typing import ConfigType

from .const import CONF_AUTH_CODE, CONF_USER_ID, DOMAIN, LOGGER

STEP_INPUT_AUTH_CODE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_AUTH_CODE): cv.string,
    }
)


class SimpliSafeOAuthValues(NamedTuple):
    """Define a named tuple to handle SimpliSafe OAuth strings."""

    code_verifier: str
    auth_url: str


@callback
def async_get_simplisafe_oauth_values() -> SimpliSafeOAuthValues:
    """Get a SimpliSafe OAuth code verifier and auth URL."""
    code_verifier = get_auth0_code_verifier()
    code_challenge = get_auth0_code_challenge(code_verifier)
    auth_url = get_auth_url(code_challenge)
    return SimpliSafeOAuthValues(code_verifier, auth_url)


class SimpliSafeFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a SimpliSafe config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._errors: dict[str, Any] = {}
        self._oauth_values: SimpliSafeOAuthValues = async_get_simplisafe_oauth_values()
        self._reauth: bool = False
        self._username: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> SimpliSafeOptionsFlowHandler:
        """Define the config flow to handle options."""
        return SimpliSafeOptionsFlowHandler(config_entry)

    async def async_step_input_auth_code(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the input of a SimpliSafe OAuth authorization code."""
        if user_input is None:
            return self.async_show_form(
                step_id="input_auth_code", data_schema=STEP_INPUT_AUTH_CODE_SCHEMA
            )

        if TYPE_CHECKING:
            assert self._oauth_values

        self._errors = {}
        session = aiohttp_client.async_get_clientsession(self.hass)

        try:
            simplisafe = await API.async_from_auth(
                user_input[CONF_AUTH_CODE],
                self._oauth_values.code_verifier,
                session=session,
            )
        except InvalidCredentialsError:
            self._errors = {"base": "invalid_auth"}
        except SimplipyError as err:
            LOGGER.error("Unknown error while logging into SimpliSafe: %s", err)
            self._errors = {"base": "unknown"}

        if self._errors:
            return await self.async_step_user()

        data = {CONF_USER_ID: simplisafe.user_id, CONF_TOKEN: simplisafe.refresh_token}
        unique_id = str(simplisafe.user_id)

        if self._reauth:
            # "Old" config entries utilized the user's email address (username) as the
            # unique ID, whereas "new" config entries utilize the SimpliSafe user ID –
            # either one is a candidate for re-auth:
            existing_entry = await self.async_set_unique_id(self._username or unique_id)

            if existing_entry:
                self.hass.config_entries.async_update_entry(
                    existing_entry, unique_id=unique_id, data=data
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(existing_entry.entry_id)
                )
                return self.async_abort(reason="reauth_successful")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=unique_id, data=data)

    async def async_step_reauth(self, config: ConfigType) -> FlowResult:
        """Handle configuration by re-auth."""
        self._username = config.get(CONF_USERNAME)
        self._reauth = True
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the start of the config flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                errors=self._errors,
                description_placeholders={CONF_URL: self._oauth_values.auth_url},
            )

        return await self.async_step_input_auth_code()


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

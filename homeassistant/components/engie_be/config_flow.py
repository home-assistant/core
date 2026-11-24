"""Config flow for the ENGIE Belgium integration."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, override

from aioengiebelgium import (
    AuthFlow,
    EngieBeAuthenticationError,
    EngieBeClient,
    EngieBeCommunicationError,
    EngieBeError,
    EngieBeMfaError,
    MfaMethod,
)
import probatio

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import (
    CONF_MFA_METHOD,
    CONF_REFRESH_TOKEN,
    DOMAIN,
    LOGGER,
    USER_MANAGEMENT_URL,
)

_MFA_METHOD_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[method.value for method in MfaMethod],
        translation_key="mfa_method",
    )
)
_CODE_SCHEMA = probatio.Schema({probatio.Required(probatio.Secret("code")): str})
_CREDENTIALS_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_EMAIL): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
        probatio.Required(CONF_MFA_METHOD, default=MfaMethod.SMS.value): (
            _MFA_METHOD_SELECTOR
        ),
    }
)


@dataclass(frozen=True, kw_only=True)
class _PendingLogin:
    """A login that has passed the password step and waits for the MFA code."""

    client: EngieBeClient
    auth_flow: AuthFlow
    email: str
    mfa_method: MfaMethod


class EngieBeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ENGIE Belgium."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._login: _PendingLogin | None = None

    async def _async_start_authentication(
        self, user_input: dict[str, Any]
    ) -> dict[str, str]:
        """Start authentication with ENGIE Belgium and return any form errors."""
        email = user_input[CONF_EMAIL]
        mfa_method = MfaMethod(user_input[CONF_MFA_METHOD])

        session = async_create_clientsession(self.hass)
        client = EngieBeClient(session=session)
        try:
            auth_flow = await client.async_start_authentication(
                email,
                user_input[CONF_PASSWORD],
                mfa_method,
                auth_session=session,
            )
        except EngieBeAuthenticationError:
            return {"base": "invalid_auth"}
        except EngieBeCommunicationError:
            return {"base": "cannot_connect"}
        except EngieBeError:
            LOGGER.exception("Unexpected error during authentication")
            return {"base": "unknown"}
        self._login = _PendingLogin(
            client=client, auth_flow=auth_flow, email=email, mfa_method=mfa_method
        )
        return {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await self._async_start_authentication(user_input)
            if not errors:
                return await self.async_step_mfa()

        return self.async_show_form(
            step_id="user",
            data_schema=_CREDENTIALS_SCHEMA,
            description_placeholders={"user_management_url": USER_MANAGEMENT_URL},
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication when the stored tokens are rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the password and restart the MFA login."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            errors = await self._async_start_authentication(
                {
                    CONF_EMAIL: reauth_entry.data[CONF_EMAIL],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_MFA_METHOD: reauth_entry.data[CONF_MFA_METHOD],
                }
            )
            if not errors:
                return await self.async_step_mfa()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=probatio.Schema(
                {probatio.Required(probatio.Secret(CONF_PASSWORD)): str}
            ),
            description_placeholders={"email": reauth_entry.data[CONF_EMAIL]},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            errors = await self._async_start_authentication(user_input)
            if not errors:
                return await self.async_step_mfa()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                _CREDENTIALS_SCHEMA,
                {
                    CONF_EMAIL: entry.data[CONF_EMAIL],
                    CONF_MFA_METHOD: entry.data[CONF_MFA_METHOD],
                },
            ),
            description_placeholders={"user_management_url": USER_MANAGEMENT_URL},
            errors=errors,
        )

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the MFA code entry step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if TYPE_CHECKING:
                assert self._login is not None
            login = self._login
            try:
                tokens = await login.auth_flow.async_submit_mfa(user_input["code"])
            except EngieBeMfaError:
                errors["base"] = "invalid_mfa_code"
            except EngieBeAuthenticationError:
                errors["base"] = "invalid_auth"
            except EngieBeCommunicationError:
                errors["base"] = "cannot_connect"
            except EngieBeError:
                LOGGER.exception("Unexpected error during MFA submission")
                errors["base"] = "unknown"
            else:
                return await self._async_finish_login(login, *tokens)

        return self.async_show_form(
            step_id="mfa", data_schema=_CODE_SCHEMA, errors=errors
        )

    async def _async_finish_login(
        self, login: _PendingLogin, access_token: str, refresh_token: str
    ) -> ConfigFlowResult:
        """Create the entry, or update and reload it, after a successful login."""
        if (subject := login.client.subject) is None:
            return self.async_show_form(
                step_id="mfa",
                data_schema=_CODE_SCHEMA,
                errors={"base": "invalid_auth"},
            )
        await self.async_set_unique_id(subject)
        self._abort_if_unique_id_mismatch()
        token_data = {
            CONF_ACCESS_TOKEN: access_token,
            CONF_REFRESH_TOKEN: refresh_token,
        }
        data = {
            CONF_EMAIL: login.email,
            CONF_MFA_METHOD: login.mfa_method.value,
            **token_data,
        }
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data_updates=token_data
            )
        if self.source == SOURCE_RECONFIGURE:
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(), data_updates=data, title=login.email
            )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=login.email, data=data)

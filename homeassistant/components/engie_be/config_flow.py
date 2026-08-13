"""Config flow for the ENGIE Belgium integration."""

from collections.abc import Mapping
from typing import Any, override

from aioengiebelgium import (
    AuthFlow,
    EngieBeAuthenticationError,
    EngieBeClient,
    EngieBeCommunicationError,
    EngieBeError,
    EngieBeMfaError,
    MfaMethod,
)
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import CONF_MFA_METHOD, CONF_REFRESH_TOKEN, DOMAIN, USER_MANAGEMENT_URL

_MFA_METHOD_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[method.value for method in MfaMethod],
        translation_key="mfa_method",
    )
)
_CODE_SCHEMA = vol.Schema({vol.Required("code"): str})


class EngieBeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ENGIE Belgium."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._username: str | None = None
        self._password: str | None = None
        self._mfa_method: MfaMethod = MfaMethod.SMS
        self._auth_flow: AuthFlow | None = None

    async def _async_start_authentication(
        self, user_input: dict[str, Any]
    ) -> dict[str, str]:
        """Start authentication with ENGIE Belgium and return any form errors."""
        self._username = user_input[CONF_USERNAME]
        self._password = user_input[CONF_PASSWORD]
        self._mfa_method = MfaMethod(user_input[CONF_MFA_METHOD])

        client = EngieBeClient(session=async_get_clientsession(self.hass))
        try:
            self._auth_flow = await client.async_start_authentication(
                self._username,
                self._password,
                self._mfa_method,
                auth_session=async_get_clientsession(self.hass),
            )
        except EngieBeAuthenticationError:
            return {"base": "invalid_auth"}
        except EngieBeCommunicationError:
            return {"base": "cannot_connect"}
        except EngieBeError:
            return {"base": "unknown"}
        return {}

    async def _async_submit_mfa(
        self, code: str
    ) -> tuple[dict[str, str], tuple[str, str] | None]:
        """Submit the MFA code and return (errors, tokens)."""
        assert self._auth_flow is not None
        try:
            tokens = await self._auth_flow.async_submit_mfa(code)
        except EngieBeMfaError:
            return {"base": "invalid_mfa_code"}, None
        except EngieBeAuthenticationError:
            return {"base": "invalid_auth"}, None
        except EngieBeCommunicationError:
            return {"base": "cannot_connect"}, None
        except EngieBeError:
            return {"base": "unknown"}, None
        return {}, tokens

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_USERNAME].lower())
            self._abort_if_unique_id_configured()

            errors = await self._async_start_authentication(user_input)
            if not errors:
                return await self.async_step_mfa()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(
                        CONF_MFA_METHOD, default=MfaMethod.SMS.value
                    ): _MFA_METHOD_SELECTOR,
                }
            ),
            description_placeholders={"user_management_url": USER_MANAGEMENT_URL},
            errors=errors,
        )

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the MFA code entry step."""
        errors: dict[str, str] = {}

        if user_input is not None and self._username is not None:
            errors, tokens = await self._async_submit_mfa(user_input["code"])
            if not errors and tokens is not None:
                access_token, refresh_token = tokens
                return self.async_create_entry(
                    title=self._username,
                    data={
                        CONF_USERNAME: self._username,
                        CONF_MFA_METHOD: self._mfa_method.value,
                        CONF_ACCESS_TOKEN: access_token,
                        CONF_REFRESH_TOKEN: refresh_token,
                    },
                )

        return self.async_show_form(
            step_id="mfa", data_schema=_CODE_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the reauthentication confirmation step."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            await self.async_set_unique_id(reauth_entry.data[CONF_USERNAME].lower())
            self._abort_if_unique_id_mismatch(reason="wrong_account")

            errors = await self._async_start_authentication(
                {
                    CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
                    CONF_PASSWORD: user_input[CONF_PASSWORD],
                    CONF_MFA_METHOD: user_input[CONF_MFA_METHOD],
                }
            )
            if not errors:
                return await self.async_step_reauth_mfa()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(
                        CONF_MFA_METHOD,
                        default=reauth_entry.data.get(
                            CONF_MFA_METHOD, MfaMethod.SMS.value
                        ),
                    ): _MFA_METHOD_SELECTOR,
                }
            ),
            description_placeholders={"username": reauth_entry.data[CONF_USERNAME]},
            errors=errors,
        )

    async def async_step_reauth_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the MFA code entry step during reauthentication."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, tokens = await self._async_submit_mfa(user_input["code"])
            if not errors and tokens is not None:
                access_token, refresh_token = tokens
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(),
                    data_updates={
                        CONF_MFA_METHOD: self._mfa_method.value,
                        CONF_ACCESS_TOKEN: access_token,
                        CONF_REFRESH_TOKEN: refresh_token,
                    },
                )

        return self.async_show_form(
            step_id="reauth_mfa", data_schema=_CODE_SCHEMA, errors=errors
        )

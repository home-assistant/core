"""Config flow to configure ecobee."""

from collections.abc import Mapping
from typing import Any

from pyecobee import (
    ECOBEE_API_KEY,
    ECOBEE_PASSWORD,
    ECOBEE_USERNAME,
    Ecobee,
    EcobeeAuthFailedError,
    EcobeeAuthMfaRequiredError,
    EcobeeAuthUnknownError,
    MfaChallenge,
)
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_CODE, CONF_PASSWORD, CONF_USERNAME

from .const import CONF_REFRESH_TOKEN, DOMAIN

_USER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_API_KEY): str,
        vol.Optional(CONF_USERNAME): str,
        vol.Optional(CONF_PASSWORD): str,
    }
)

_MFA_SCHEMA = vol.Schema({vol.Required(CONF_CODE): str})
_REAUTH_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class EcobeeFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle an ecobee config flow."""

    VERSION = 1

    _ecobee: Ecobee
    _mfa_challenge: MfaChallenge | None = None
    _pending_username: str | None = None
    _pending_password: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            api_key = user_input.get(CONF_API_KEY)
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)

            if api_key and not (username or password):
                self._ecobee = Ecobee(config={ECOBEE_API_KEY: api_key})
                if await self.hass.async_add_executor_job(self._ecobee.request_pin):
                    return await self.async_step_authorize()
                errors["base"] = "pin_request_failed"
            elif username and password and not api_key:
                self._pending_username = username
                self._pending_password = password
                self._ecobee = Ecobee(
                    config={
                        ECOBEE_USERNAME: username,
                        ECOBEE_PASSWORD: password,
                    }
                )
                try:
                    success = await self.hass.async_add_executor_job(
                        self._ecobee.refresh_tokens
                    )
                except EcobeeAuthMfaRequiredError as err:
                    self._mfa_challenge = err.args[0]
                    return await self.async_step_mfa()
                except EcobeeAuthFailedError:
                    errors["base"] = "invalid_auth"
                except EcobeeAuthUnknownError:
                    errors["base"] = "unknown"
                else:
                    if success:
                        return self._async_create_or_update_entry()
                    errors["base"] = "login_failed"
            else:
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="user",
            data_schema=_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Collect an MFA OTP code and complete the login."""
        assert self._mfa_challenge is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            code = user_input[CONF_CODE].strip()
            if not code:
                errors["base"] = "invalid_mfa_code"
            else:
                try:
                    success = await self.hass.async_add_executor_job(
                        self._ecobee.submit_mfa_code, self._mfa_challenge, code
                    )
                except EcobeeAuthFailedError:
                    errors["base"] = "invalid_mfa_code"
                except EcobeeAuthUnknownError:
                    errors["base"] = "unknown"
                else:
                    if success:
                        return self._async_create_or_update_entry()
                    errors["base"] = "invalid_mfa_code"

        return self.async_show_form(
            step_id="mfa",
            data_schema=_MFA_SCHEMA,
            errors=errors,
            description_placeholders={"mfa_type": self._mfa_challenge.mfa_type},
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Present the user with the PIN so that the app can be authorized on ecobee.com."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if await self.hass.async_add_executor_job(self._ecobee.request_tokens):
                config = {
                    CONF_API_KEY: self._ecobee.api_key,
                    CONF_REFRESH_TOKEN: self._ecobee.refresh_token,
                }
                return self.async_create_entry(title=DOMAIN, data=config)
            errors["base"] = "token_request_failed"

        return self.async_show_form(
            step_id="authorize",
            errors=errors,
            description_placeholders={
                "pin": self._ecobee.pin,
                "auth_url": "https://www.ecobee.com/consumerportal/index.html",
            },
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Perform reauth upon an ecobee authentication error."""
        self._pending_username = entry_data.get(CONF_USERNAME)
        self._pending_password = entry_data.get(CONF_PASSWORD)
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-run the web login. May surface a fresh MFA challenge."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._pending_password = user_input[CONF_PASSWORD]
            self._ecobee = Ecobee(
                config={
                    ECOBEE_USERNAME: self._pending_username,
                    ECOBEE_PASSWORD: self._pending_password,
                }
            )
            try:
                success = await self.hass.async_add_executor_job(
                    self._ecobee.refresh_tokens
                )
            except EcobeeAuthMfaRequiredError as err:
                self._mfa_challenge = err.args[0]
                return await self.async_step_mfa()
            except EcobeeAuthFailedError:
                errors["base"] = "invalid_auth"
            except EcobeeAuthUnknownError:
                errors["base"] = "unknown"
            else:
                if success:
                    return self._async_create_or_update_entry()
                errors["base"] = "login_failed"

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_REAUTH_SCHEMA,
            errors=errors,
            description_placeholders={"username": self._pending_username or ""},
        )

    def _async_create_or_update_entry(self) -> ConfigFlowResult:
        """Create a new entry or update the existing one on reauth."""
        data = {
            CONF_USERNAME: self._pending_username,
            CONF_PASSWORD: self._pending_password,
            CONF_REFRESH_TOKEN: self._ecobee.refresh_token,
        }
        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(
                self._get_reauth_entry(), data=data
            )
        return self.async_create_entry(title=DOMAIN, data=data)

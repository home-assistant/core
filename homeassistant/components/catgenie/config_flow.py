"""Config flow for the CatGenie integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from catgenie import CatGenieAuth
from catgenie.exceptions import CatGenieAuthenticationError, CatGenieException
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_CODE, CONF_COUNTRY_CODE, CONF_TOKEN

from .const import DOMAIN, LOGGER

CONF_PHONE = "phone"

STEP_PHONE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COUNTRY_CODE): int,
        vol.Required(CONF_PHONE): str,
    }
)

STEP_CODE_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CODE): str,
    }
)


class CatGenieConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CatGenie."""

    VERSION = 1

    _country_code: int
    _phone: str

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the phone number step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._country_code = user_input[CONF_COUNTRY_CODE]
            self._phone = user_input[CONF_PHONE]

            try:
                async with CatGenieAuth() as auth:
                    await auth.request_login_code(
                        country_code=self._country_code,
                        phone=self._phone,
                    )
            except CatGenieAuthenticationError:
                errors["base"] = "cannot_connect"
            except CatGenieException:
                LOGGER.exception("Unexpected exception requesting login code")
                errors["base"] = "unknown"
            else:
                return await self.async_step_code()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_PHONE_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the SMS verification code step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                async with CatGenieAuth() as auth:
                    credentials = await auth.login(
                        country_code=self._country_code,
                        phone=self._phone,
                        code=user_input[CONF_CODE],
                    )
            except CatGenieAuthenticationError:
                errors["base"] = "invalid_auth"
            except CatGenieException:
                LOGGER.exception("Unexpected exception during login")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(credentials.user_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"CatGenie ({self._phone})",
                    data={CONF_TOKEN: credentials.refresh_token},
                )

        return self.async_show_form(
            step_id=CONF_CODE,
            data_schema=STEP_CODE_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication when the token is rejected."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-auth: collect phone number and request a new SMS code."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._country_code = user_input[CONF_COUNTRY_CODE]
            self._phone = user_input[CONF_PHONE]

            try:
                async with CatGenieAuth() as auth:
                    await auth.request_login_code(
                        country_code=self._country_code,
                        phone=self._phone,
                    )
            except CatGenieAuthenticationError:
                errors["base"] = "cannot_connect"
            except CatGenieException:
                LOGGER.exception("Unexpected exception requesting login code")
                errors["base"] = "unknown"
            else:
                return await self.async_step_reauth_code()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_PHONE_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_reauth_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-auth: enter the new SMS code."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                async with CatGenieAuth() as auth:
                    credentials = await auth.login(
                        country_code=self._country_code,
                        phone=self._phone,
                        code=user_input[CONF_CODE],
                    )
            except CatGenieAuthenticationError:
                errors["base"] = "invalid_auth"
            except CatGenieException:
                LOGGER.exception("Unexpected exception during re-auth login")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(credentials.user_id)
                self._abort_if_unique_id_mismatch(reason="reauth_account_mismatch")
                reauth_entry = self._get_reauth_entry()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={CONF_TOKEN: credentials.refresh_token},
                )

        return self.async_show_form(
            step_id="reauth_code",
            data_schema=STEP_CODE_DATA_SCHEMA,
            errors=errors,
        )

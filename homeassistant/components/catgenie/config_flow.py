"""Config flow for the CatGenie integration."""

from __future__ import annotations

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

            auth = CatGenieAuth()
            try:
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
            auth = CatGenieAuth()
            try:
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

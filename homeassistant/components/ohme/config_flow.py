"""Config flow for ohme integration."""

from collections.abc import Mapping
from typing import Any

from ohme import ApiException, AuthException, OhmeApiClient
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.EMAIL,
                autocomplete="email",
            ),
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            ),
        ),
    }
)


class OhmeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow."""

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """First config step."""

        errors: dict[str, str] = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_EMAIL: user_input[CONF_EMAIL]})

            errors = await self._validate_account(
                user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
            )
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_EMAIL], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=USER_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle re-authentication confirmation."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None:
            errors = await self._validate_account(
                reauth_entry.data[CONF_EMAIL],
                user_input[CONF_PASSWORD],
            )
            if not errors:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates=user_input,
                )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=REAUTH_SCHEMA,
            description_placeholders={"email": reauth_entry.data[CONF_EMAIL]},
            errors=errors,
        )

    async def _validate_account(self, email: str, password: str) -> dict[str, str]:
        """Validate Ohme account and return dict of errors."""
        errors: dict[str, str] = {}
        client = OhmeApiClient(
            email,
            password,
        )
        try:
            await client.async_login()
        except AuthException:
            errors["base"] = "invalid_auth"
        except ApiException:
            errors["base"] = "unknown"

        return errors

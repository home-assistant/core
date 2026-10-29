"""Config flow for the Sunsynk integration."""

from collections.abc import Mapping
from typing import Any, override

import probatio
from sunsynk.client import SunsynkClient
from sunsynk.exceptions import SunsynkAuthenticationError, SunsynkConnectionError
from sunsynk.user import User

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import DOMAIN

PASSWORD_SELECTOR = TextSelector(
    TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="current-password")
)

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_USERNAME): TextSelector(
            TextSelectorConfig(type=TextSelectorType.EMAIL, autocomplete="username")
        ),
        probatio.Required(probatio.Secret(CONF_PASSWORD)): PASSWORD_SELECTOR,
    }
)

STEP_REAUTH_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(probatio.Secret(CONF_PASSWORD)): PASSWORD_SELECTOR,
    }
)


class SunsynkConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sunsynk."""

    VERSION = 1

    async def _async_get_user(
        self, username: str, password: str
    ) -> tuple[User | None, dict[str, str]]:
        """Validate the credentials and return the account user."""
        client = SunsynkClient(
            username, password, session=async_get_clientsession(self.hass)
        )
        try:
            user = await client.get_user()
        except SunsynkAuthenticationError:
            return None, {"base": "invalid_auth"}
        except SunsynkConnectionError:
            return None, {"base": "cannot_connect"}
        return user, {}

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            user, errors = await self._async_get_user(
                user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
            )
            if user is not None:
                await self.async_set_unique_id(str(user.id))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with a new password."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        username = reauth_entry.data[CONF_USERNAME]
        if user_input is not None:
            user, errors = await self._async_get_user(
                username, user_input[CONF_PASSWORD]
            )
            if user is not None:
                await self.async_set_unique_id(str(user.id))
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PASSWORD: user_input[CONF_PASSWORD]},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            description_placeholders={CONF_USERNAME: username},
            errors=errors,
        )

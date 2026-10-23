"""Config flow for the Helty Flow Cloud integration."""

from collections.abc import Mapping
from typing import Any, override

import probatio
from pyheltycloud import HeltyCloud, HeltyCloudAuthError, HeltyCloudError

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_EMAIL): str,
        probatio.Required(probatio.Secret(CONF_PASSWORD)): str,
    }
)


class HeltyCloudConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Helty Flow Cloud."""

    async def _async_login(
        self, user_input: dict[str, Any], errors: dict[str, str]
    ) -> str | None:
        """Sign in and return the account id, or fill in errors."""
        client = HeltyCloud(
            user_input[CONF_EMAIL],
            user_input[CONF_PASSWORD],
            session=async_get_clientsession(self.hass),
        )
        try:
            await client.login()
        except HeltyCloudAuthError:
            errors["base"] = "invalid_auth"
            return None
        except HeltyCloudError:
            errors["base"] = "cannot_connect"
            return None
        return client.user_id

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}
        if user_input is not None and (
            user_id := await self._async_login(user_input, errors)
        ):
            # The email is only a login alias of the account and can
            # change; the Cognito subject cannot.
            await self.async_set_unique_id(user_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_EMAIL], data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle credentials the cloud no longer accepts."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the credentials again.

        The email is asked as well as the password: it is only an alias of
        the account, so it may be the one that changed.
        """
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        if user_input is not None and (
            user_id := await self._async_login(user_input, errors)
        ):
            await self.async_set_unique_id(user_id)
            self._abort_if_unique_id_mismatch()
            return self.async_update_reload_and_abort(
                reauth_entry, title=user_input[CONF_EMAIL], data_updates=user_input
            )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                {CONF_EMAIL: reauth_entry.data[CONF_EMAIL]},
            ),
            errors=errors,
        )

"""Config flow for the Hydrawise integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from aiohttp import ClientError
from pydrawise import auth as pydrawise_auth, hybrid
from pydrawise.exceptions import NotAuthorizedError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME

from .const import APP_ID, DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_API_KEY): str,
    }
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_PASSWORD): str, vol.Required(CONF_API_KEY): str}
)


class HydrawiseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hydrawise."""

    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup."""
        if user_input is None:
            return self._show_user_form({})
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        api_key = user_input[CONF_API_KEY]
        unique_id, errors = await _authenticate(username, password, api_key)
        if errors:
            return self._show_user_form(errors)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=username,
            data={
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONF_API_KEY: api_key,
            },
        )

    def _show_user_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauth upon an API authentication error."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            return self._show_reauth_form({})

        reauth_entry = self._get_reauth_entry()
        username = reauth_entry.data[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        api_key = user_input[CONF_API_KEY]
        user_id, errors = await _authenticate(username, password, api_key)
        if user_id is None:
            return self._show_reauth_form(errors)

        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_mismatch(reason="wrong_account")
        return self.async_update_reload_and_abort(
            reauth_entry,
            data={
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
                CONF_API_KEY: api_key,
            },
        )

    def _show_reauth_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        return self.async_show_form(
            step_id="reauth_confirm", data_schema=STEP_REAUTH_DATA_SCHEMA, errors=errors
        )


async def _authenticate(
    username: str, password: str, api_key: str
) -> tuple[str | None, dict[str, str]]:
    """Authenticate with the Hydrawise API."""
    unique_id = None
    errors: dict[str, str] = {}
    auth = pydrawise_auth.HybridAuth(username, password, api_key)
    try:
        await auth.check()
    except NotAuthorizedError:
        errors["base"] = "invalid_auth"
    except TimeoutError:
        errors["base"] = "timeout_connect"

    if errors:
        return unique_id, errors

    try:
        api = hybrid.HybridClient(auth, app_id=APP_ID)
        # Don't fetch zones because we don't need them yet.
        user = await api.get_user(fetch_zones=False)
    except TimeoutError:
        errors["base"] = "timeout_connect"
    except ClientError as ex:
        LOGGER.error("Unable to connect to Hydrawise cloud service: %s", ex)
        errors["base"] = "cannot_connect"
    else:
        unique_id = f"hydrawise-{user.customer_id}"

    return unique_id, errors

"""Config flow for Schlage integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pyschlage
from pyschlage.exceptions import NotAuthorizedError
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class SchlageConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Schlage."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self._show_user_form({})
        username = user_input[CONF_USERNAME].lower()
        password = user_input[CONF_PASSWORD]
        user_id, errors = await self.hass.async_add_executor_job(
            _authenticate, username, password
        )
        if user_id is None:
            return self._show_user_form(errors)

        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=username,
            data={
                CONF_USERNAME: username,
                CONF_PASSWORD: password,
            },
        )

    def _show_user_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        """Show the user form."""
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
        user_id, errors = await self.hass.async_add_executor_job(
            _authenticate, username, password
        )
        if user_id is None:
            return self._show_reauth_form(errors)

        await self.async_set_unique_id(user_id)
        self._abort_if_unique_id_mismatch(reason="wrong_account")

        data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: user_input[CONF_PASSWORD],
        }
        return self.async_update_reload_and_abort(reauth_entry, data=data)

    def _show_reauth_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        """Show the reauth form."""
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_REAUTH_DATA_SCHEMA,
            errors=errors,
        )


def _authenticate(username: str, password: str) -> tuple[str | None, dict[str, str]]:
    """Authenticate with the Schlage API."""
    user_id = None
    errors: dict[str, str] = {}
    try:
        auth = pyschlage.Auth(username, password)
        auth.authenticate()
    except NotAuthorizedError:
        errors["base"] = "invalid_auth"
    except Exception:  # noqa: BLE001
        LOGGER.exception("Unknown error")
        errors["base"] = "unknown"
    else:
        # The user_id property will make a blocking call if it's not already
        # cached. To avoid blocking the event loop, we read it here.
        user_id = auth.user_id
    return user_id, errors

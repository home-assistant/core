"""Config flow for Schlage integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pyschlage
from pyschlage.exceptions import NotAuthorizedError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, LOGGER

STEP_USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
)
STEP_REAUTH_DATA_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Schlage."""

    VERSION = 1

    reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self._show_user_form({})
        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        user_id, errors = await self.hass.async_add_executor_job(
            _authenticate, username, password
        )
        if user_id is None:
            return self._show_user_form(errors)

        await self.async_set_unique_id(user_id)
        return self.async_create_entry(title=username, data=user_input)

    def _show_user_form(self, errors: dict[str, str]) -> FlowResult:
        """Show the user form."""
        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Handle reauth upon an API authentication error."""
        self.reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Dialog that informs the user that reauth is required."""
        assert self.reauth_entry is not None
        if user_input is None:
            return self._show_reauth_form({})

        username = self.reauth_entry.data[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]
        user_id, errors = await self.hass.async_add_executor_job(
            _authenticate, username, password
        )
        if user_id is None:
            return self._show_reauth_form(errors)

        if self.reauth_entry.unique_id != user_id:
            return self.async_abort(reason="wrong_account")

        data = {
            CONF_USERNAME: username,
            CONF_PASSWORD: user_input[CONF_PASSWORD],
        }
        self.hass.config_entries.async_update_entry(self.reauth_entry, data=data)
        await self.hass.config_entries.async_reload(self.reauth_entry.entry_id)
        return self.async_abort(reason="reauth_successful")

    def _show_reauth_form(self, errors: dict[str, str]) -> FlowResult:
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
    except Exception:  # pylint: disable=broad-except
        LOGGER.exception("Unknown error")
        errors["base"] = "unknown"
    else:
        # The user_id property will make a blocking call if it's not already
        # cached. To avoid blocking the event loop, we read it here.
        user_id = auth.user_id
    return user_id, errors

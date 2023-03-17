"""Config flow for pushover integration."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pushover_complete import BadAPIRequestError, PushoverAPI
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_USER_KEY, DEFAULT_NAME, DOMAIN

USER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_API_KEY): str,
        vol.Required(CONF_USER_KEY): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, str]:
    """Validate user input."""
    errors = {}
    pushover_api = PushoverAPI(data[CONF_API_KEY])
    try:
        await hass.async_add_executor_job(pushover_api.validate, data[CONF_USER_KEY])
    except BadAPIRequestError as err:
        if "application token is invalid" in str(err):
            errors[CONF_API_KEY] = "invalid_api_key"
        elif "user key is invalid" in str(err):
            errors[CONF_USER_KEY] = "invalid_user_key"
        else:
            errors["base"] = "cannot_connect"
    return errors


class PushBulletConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for pushover integration."""

    _reauth_entry: config_entries.ConfigEntry | None

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Perform reauth upon an API authentication error."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Confirm reauth dialog."""
        errors = {}
        if user_input is not None and self._reauth_entry:
            user_input = {**self._reauth_entry.data, **user_input}
            self._async_abort_entries_match(
                {
                    CONF_USER_KEY: user_input[CONF_USER_KEY],
                    CONF_API_KEY: user_input[CONF_API_KEY],
                }
            )
            errors = await validate_input(self.hass, user_input)
            if not errors:
                self.hass.config_entries.async_update_entry(
                    self._reauth_entry, data=user_input
                )
                await self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): str,
                }
            ),
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match(
                {
                    CONF_USER_KEY: user_input[CONF_USER_KEY],
                    CONF_API_KEY: user_input[CONF_API_KEY],
                }
            )
            self._async_abort_entries_match({CONF_NAME: user_input[CONF_NAME]})

            errors = await validate_input(self.hass, user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=USER_SCHEMA,
            errors=errors,
        )

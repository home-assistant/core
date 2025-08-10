"""Config flow to configure the SmartTub integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from smarttub import LoginFailed
import voluptuous as vol

from homeassistant.config_entries import SOURCE_REAUTH, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from .const import DOMAIN
from .controller import SmartTubController

DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
)


class SmartTubConfigFlow(ConfigFlow, domain=DOMAIN):
    """SmartTub configuration flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initiated by the user."""
        errors = {}

        if user_input is not None:
            controller = SmartTubController(self.hass)
            try:
                account = await controller.login(
                    user_input[CONF_EMAIL], user_input[CONF_PASSWORD]
                )

            except LoginFailed:
                errors["base"] = "invalid_auth"
            else:
                await self.async_set_unique_id(account.id)

                if self.source != SOURCE_REAUTH:
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=user_input[CONF_EMAIL], data=user_input
                    )

                # this is a reauth attempt
                self._abort_if_unique_id_mismatch(reason="already_configured")
                return self.async_update_reload_and_abort(
                    self._get_reauth_entry(), data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Get new credentials if the current ones don't work anymore."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> ConfigFlowResult:
        """Dialog that informs the user that reauth is required."""
        if user_input is None:
            # same as DATA_SCHEMA but with default email
            data_schema = vol.Schema(
                {
                    vol.Required(
                        CONF_EMAIL,
                        default=self._get_reauth_entry().data.get(CONF_EMAIL),
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            )
            return self.async_show_form(
                step_id="reauth_confirm",
                data_schema=data_schema,
            )
        return await self.async_step_user(user_input)

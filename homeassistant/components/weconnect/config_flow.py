"""Config flow for WeConnect integration."""

from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from weconnect import weconnect
from weconnect.errors import APIError, AuthentificationError

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .const import CONF_SPIN, DOMAIN

DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_SPIN, default=""): str,
    }
)


class WeConnectConfigFlow(ConfigFlow, domain=DOMAIN):
    """WeConnect config flow."""

    _reauth_entry: ConfigEntry | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        client = weconnect.WeConnect(
            user_input[CONF_USERNAME],
            user_input[CONF_PASSWORD],
            spin=user_input[CONF_SPIN],
            loginOnInit=False,
            updateAfterLogin=False,
        )

        try:
            await self.hass.async_add_executor_job(client.login)
        except AuthentificationError:
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={"base": "invalid_auth"},
            )
        except APIError:
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={"base": "cannot_connect"},
            )

        if self._reauth_entry:
            self.hass.config_entries.async_update_entry(
                self._reauth_entry, data=user_input
            )
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self._reauth_entry.entry_id)
            )
            return self.async_abort(reason="reauth_successful")

        await self.async_set_unique_id(user_input[CONF_USERNAME])
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=user_input[CONF_USERNAME], data=user_input)

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle user re-authentication."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )

        return await self.async_step_user()

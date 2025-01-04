"""Config flow for Bizkaibus integration."""

from typing import Any

from homeassistant import config_entries

from . import CONFIG_SCHEMA
from .const import CONF_STOP_ID, DOMAIN


class BizkaibusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bizkaibus."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the user step of the config flow."""
        if user_input is not None:
            return self.async_create_entry(
                title="Parada " + user_input[CONF_STOP_ID],
                data={CONF_STOP_ID: user_input[CONF_STOP_ID]},
            )

        return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle reconfiguration of the entry."""
        if user_input is not None:
            await self.async_set_unique_id("user")
            self._abort_if_unique_id_mismatch(reason="wrong_account")
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                data_updates=user_input[CONF_STOP_ID],
            )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=CONFIG_SCHEMA,
        )

    async def async_step_import(self, info) -> config_entries.ConfigFlowResult:
        """Handle the import step of the config flow."""
        if info is not None:
            pass

        return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)

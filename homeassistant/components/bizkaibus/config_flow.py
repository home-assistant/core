"""Config flow for Bizkaibus integration."""

from typing import Any

from bizkaibus.bizkaibusAPI import BizkaibusAPI, BizkaibusLanguages
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
import homeassistant.helpers.config_validation as cv

from .const import CONF_STOP_ID, DOMAIN, LINE_ID

USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_STOP_ID): cv.string,
        vol.Optional(LINE_ID): cv.string,
    }
)


class BizkaibusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bizkaibus."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step of the config flow."""
        if user_input:
            api = BizkaibusAPI(BizkaibusLanguages.ES, user_input[CONF_STOP_ID])

            isOnline = await api.TestConnection()
            if isOnline:
                bizkaibus_lines = await api.GetLinesOnStop()
                lines = [line.id for line in bizkaibus_lines]

                timetable = await api.GetTimetable()

                if timetable is not None:
                    title = f"{user_input[CONF_STOP_ID]} {timetable.name if timetable.name is not None else timetable.id}"
                else:
                    title = f"{DOMAIN.capitalize()} {user_input[CONF_STOP_ID]}"

                return self.async_create_entry(
                    title=title, data=user_input, options={"lines": lines}
                )

        return self.async_show_form(step_id="user", data_schema=USER_DATA_SCHEMA)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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
            data_schema=USER_DATA_SCHEMA,
        )

    async def async_step_import(self, info) -> ConfigFlowResult:
        """Handle the import step of the config flow."""
        if info is not None:
            pass

        return self.async_show_form(step_id="user", data_schema=USER_DATA_SCHEMA)

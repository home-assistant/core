"""Config flow for Bizkaibus integration."""

from typing import Any, override

from bizkaibus.bizkaibusAPI import BizkaibusAPI, BizkaibusLanguages
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import CONF_LINE_IDS, CONF_LINES, CONF_STOP_ID, DOMAIN

USER_DATA_SCHEMA = vol.Schema({vol.Required(CONF_STOP_ID): cv.string})


class BizkaibusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bizkaibus."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow state."""
        self._line_ids: list[str] = []
        self._lines: dict[str, Any] = {}
        self._title = ""
        self._stop_id = ""

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step of the config flow."""
        if user_input:
            self._stop_id = user_input[CONF_STOP_ID]
            api = BizkaibusAPI(BizkaibusLanguages.ES, self._stop_id)

            is_online = await api.TestConnection()
            if is_online:
                bizkaibus_lines = await api.GetLinesOnStop()

                self._line_ids = [line.id for line in bizkaibus_lines]
                self._lines = {line.id: line.route for line in bizkaibus_lines}

                timetable = await api.GetTimetable()

                if timetable is not None:
                    self._title = f"{user_input[CONF_STOP_ID]} {timetable.name if timetable.name is not None else timetable.id}"
                else:
                    self._title = f"{DOMAIN.capitalize()} {user_input[CONF_STOP_ID]}"

                return await self.async_step_lines(user_input=user_input)

        return self.async_show_form(step_id="user", data_schema=USER_DATA_SCHEMA)

    async def async_step_lines(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select bus lines."""
        if user_input is not None and CONF_LINE_IDS in user_input:
            return self.async_create_entry(
                title=self._title,
                data={CONF_STOP_ID: self._stop_id},
                options={
                    CONF_LINE_IDS: user_input[CONF_LINE_IDS],
                    CONF_LINES: self._lines,
                },
            )

        options = [
            selector.SelectOptionDict(
                value=line,
                label=f"{line} - {self._lines[line]}",
            )
            for line in self._line_ids
        ]

        return self.async_show_form(
            step_id="lines",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_STOP_ID, default=self._stop_id): cv.string,
                    vol.Required(CONF_LINE_IDS): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    ),
                }
            ),
        )

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

        return self.async_show_form(step_id="import", data_schema=USER_DATA_SCHEMA)

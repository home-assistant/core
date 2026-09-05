"""Config flow for Bizkaibus integration."""

from typing import Any, override

from bizkaibus.bizkaibusAPI import BizkaibusAPI, BizkaibusLanguages
import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import CONF_LINE_IDS, CONF_LINES, CONF_STOP_ID, DOMAIN

USER_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_STOP_ID): vol.All(cv.string, vol.Match(r"^[0-9]{4}$"))}
)


def _lines_schema(
    line_ids: list[str], lines: dict[str, Any], selected_line_ids: list[str]
) -> vol.Schema:
    """Return the schema for selecting bus lines."""
    options = [
        selector.SelectOptionDict(
            value=line,
            label=f"{line} - {lines[line]}",
        )
        for line in line_ids
    ]

    return vol.Schema(
        {
            vol.Required(
                CONF_LINE_IDS, default=selected_line_ids
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    multiple=True,
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
        }
    )


async def _async_get_lines(
    stop_id: str,
) -> tuple[BizkaibusAPI | None, list[str], dict[str, Any]]:
    """Fetch the available lines for a bus stop."""
    api = BizkaibusAPI(BizkaibusLanguages.ES, stop_id)
    if not await api.TestConnection():
        return None, [], {}

    bizkaibus_lines = await api.GetLinesOnStop()
    return (
        api,
        [line.id for line in bizkaibus_lines],
        {line.id: line.route for line in bizkaibus_lines},
    )


class BizkaibusConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bizkaibus."""

    VERSION = 1

    @staticmethod
    @callback
    @override
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowWithReload:
        """Get the options flow."""
        return BizkaibusOptionsFlow()

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
        errors: dict[str, str] = {}

        if user_input:
            self._stop_id = user_input[CONF_STOP_ID]

            await self.async_set_unique_id(self._stop_id)
            self._abort_if_unique_id_configured()

            api, self._line_ids, self._lines = await _async_get_lines(self._stop_id)
            if api is None:
                errors["base"] = "cannot_connect"
            else:
                timetable = await api.GetTimetable()

                if timetable is not None:
                    self._title = f"{user_input[CONF_STOP_ID]} {timetable.name if timetable.name is not None else timetable.id}"
                else:
                    self._title = f"{DOMAIN.capitalize()} {user_input[CONF_STOP_ID]}"

                return await self.async_step_lines(user_input=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_lines(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select bus lines."""
        if user_input is not None and CONF_LINE_IDS in user_input:
            if self.source == SOURCE_RECONFIGURE:
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    unique_id=self._stop_id,
                    title=self._title,
                    data_updates={CONF_STOP_ID: self._stop_id},
                    options={
                        CONF_LINE_IDS: user_input[CONF_LINE_IDS],
                        CONF_LINES: self._lines,
                    },
                )

            return self.async_create_entry(
                title=self._title,
                data={CONF_STOP_ID: self._stop_id},
                options={
                    CONF_LINE_IDS: user_input[CONF_LINE_IDS],
                    CONF_LINES: self._lines,
                },
            )

        return self.async_show_form(
            step_id="lines",
            data_schema=_lines_schema(self._line_ids, self._lines, []),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the entry."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            stop_id = user_input[CONF_STOP_ID]

            if stop_id != reconfigure_entry.data[CONF_STOP_ID]:
                await self.async_set_unique_id(stop_id)
                self._abort_if_unique_id_configured()

            api, self._line_ids, self._lines = await _async_get_lines(stop_id)
            if api is None:
                errors["base"] = "cannot_connect"
            else:
                timetable = await api.GetTimetable()
                self._stop_id = stop_id
                self._title = (
                    f"{stop_id} {timetable.name if timetable.name is not None else timetable.id}"
                    if timetable is not None
                    else f"{DOMAIN.capitalize()} {stop_id}"
                )
                return await self.async_step_lines()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                USER_DATA_SCHEMA, reconfigure_entry.data
            ),
            errors=errors,
        )

    async def async_step_import(self, info: dict[str, Any]) -> ConfigFlowResult:
        """Handle the import step of the config flow."""
        if not info or CONF_STOP_ID not in info:
            return self.async_abort(reason="invalid_stop_id")

        stop_id = info[CONF_STOP_ID]
        await self.async_set_unique_id(stop_id)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=stop_id,
            data={CONF_STOP_ID: stop_id},
        )


class BizkaibusOptionsFlow(OptionsFlowWithReload):
    """Handle Bizkaibus options."""

    def __init__(self) -> None:
        """Initialize the options flow."""
        self._line_ids: list[str] = []
        self._lines: dict[str, Any] = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the selected bus lines."""
        errors: dict[str, str] = {}

        if user_input is not None and not errors:
            return self.async_create_entry(
                title="",
                data={
                    CONF_LINE_IDS: user_input[CONF_LINE_IDS],
                    CONF_LINES: self._lines,
                },
            )

        api, self._line_ids, self._lines = await _async_get_lines(
            self.config_entry.data[CONF_STOP_ID]
        )
        if api is None:
            errors["base"] = "cannot_connect"

        selected_line_ids = self.config_entry.options.get(CONF_LINE_IDS, [])
        return self.async_show_form(
            step_id="init",
            data_schema=_lines_schema(self._line_ids, self._lines, selected_line_ids),
            errors=errors,
        )

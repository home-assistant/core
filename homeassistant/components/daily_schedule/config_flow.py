"""Config flow for daily schedule integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import ATTR_END, ATTR_SCHEDULE, ATTR_START, DOMAIN
from .schedule import Schedule

ADD_PERIOD = "add_period"
PERIOD_DELIMITER = " - "

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): selector.TextSelector(),
        vol.Required(ADD_PERIOD, default=True): selector.BooleanSelector(),
    }
)
CONFIG_PERIOD = vol.Schema(
    {
        vol.Required(ATTR_START, default="00:00:00"): selector.TimeSelector(),
        vol.Required(ATTR_END, default="00:00:00"): selector.TimeSelector(),
        vol.Required(ADD_PERIOD, default=False): selector.BooleanSelector(),
    }
)
OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_START, default="00:00:00"): selector.TimeSelector(),
        vol.Optional(ATTR_END, default="00:00:00"): selector.TimeSelector(),
    }
)


class DailyScheduleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config flow."""

    def __init__(self):
        """Initialize a new flow."""
        self.options: dict[str, Any] = {ATTR_SCHEDULE: []}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=CONFIG_SCHEMA)

        if user_input.get(ADD_PERIOD, False):
            self.options[CONF_NAME] = user_input[CONF_NAME]
            return await self.async_step_period()

        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data={},
            options={ATTR_SCHEDULE: []},
        )

    async def async_step_period(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle adding a time period."""
        errors: dict[str, str] = {}

        if user_input is not None:

            # Validate the new schedule.
            time_periods = self.options[ATTR_SCHEDULE].copy()
            time_periods.append(
                {ATTR_START: user_input[ATTR_START], ATTR_END: user_input[ATTR_END]}
            )
            try:
                schedule = Schedule(time_periods)
            except vol.Invalid:
                errors["base"] = "invalid_schedule"

            if not errors:
                self.options[ATTR_SCHEDULE] = schedule.to_list()

                if user_input.get(ADD_PERIOD, False):
                    return await self.async_step_period()

                return self.async_create_entry(
                    title=self.options[CONF_NAME],
                    data={},
                    options={ATTR_SCHEDULE: self.options[ATTR_SCHEDULE]},
                )

        return self.async_show_form(
            step_id="period", data_schema=CONFIG_PERIOD, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlowHandler:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle an options flow."""
        errors: dict[str, str] = {}

        if user_input is not None:

            # Get all periods except for the ones which were unchecked by the user.
            time_periods = [
                {
                    ATTR_START: period.split(PERIOD_DELIMITER)[0],
                    ATTR_END: period.split(PERIOD_DELIMITER)[1],
                }
                for period in user_input.get(ATTR_SCHEDULE, [])
            ]

            # Add the additional period.
            if user_input.get(ADD_PERIOD, True):
                time_periods.append(
                    {
                        ATTR_START: user_input.get(ATTR_START, "00:00:00"),
                        ATTR_END: user_input.get(ATTR_END, "00:00:00"),
                    }
                )

            try:
                schedule = Schedule(time_periods)
            except vol.Invalid:
                errors["base"] = "invalid_schedule"

            if not errors:
                return self.async_create_entry(
                    title="",
                    data={ATTR_SCHEDULE: schedule.to_list()},
                )

        periods = [
            f"{period[ATTR_START]}{PERIOD_DELIMITER}{period[ATTR_END]}"
            for period in self.config_entry.options.get(ATTR_SCHEDULE, [])
        ]
        if periods:
            schema = vol.Schema(
                {
                    vol.Required(ATTR_SCHEDULE, default=periods): cv.multi_select(
                        periods
                    ),
                    vol.Required(ADD_PERIOD, default=False): cv.boolean,
                }
            ).extend(OPTIONS_SCHEMA.schema)
        else:
            schema = OPTIONS_SCHEMA

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)

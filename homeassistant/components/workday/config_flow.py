"""Adds config flow for Workday integration."""
from __future__ import annotations

from typing import Any

import holidays
from holidays import HolidayBase
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from homeassistant.util import dt

from .const import (
    ALLOWED_DAYS,
    CONF_ADD_HOLIDAYS,
    CONF_COUNTRY,
    CONF_EXCLUDES,
    CONF_OFFSET,
    CONF_PROVINCE,
    CONF_REMOVE_HOLIDAYS,
    CONF_WORKDAYS,
    DEFAULT_EXCLUDES,
    DEFAULT_NAME,
    DEFAULT_OFFSET,
    DEFAULT_WORKDAYS,
    DOMAIN,
)


def add_province_to_schema(
    schema: vol.Schema,
    options: dict[str, Any],
) -> vol.Schema:
    """Update schema with province from country."""
    year: int = dt.now().year
    obj_holidays: HolidayBase = getattr(holidays, options[CONF_COUNTRY])(years=year)
    new_schema = schema

    if hasattr(obj_holidays, "subdivisions"):
        div_list = obj_holidays.subdivisions
        div_list.insert(0, "")
        add_schema = {
            vol.Optional(CONF_PROVINCE): SelectSelector(
                SelectSelectorConfig(
                    options=div_list,
                    mode=SelectSelectorMode.DROPDOWN,
                )
            ),
        }

        new_schema = vol.Schema({**DATA_SCHEMA_OPT.schema, **add_schema})
    return new_schema


def validate_custom_dates(user_input: dict[str, Any]) -> None:
    """Validate custom dates for add/remove holidays."""

    for add_date in user_input[CONF_ADD_HOLIDAYS]:
        if dt.parse_date(add_date) is None:
            raise AddDatesError("Incorrect date")

    year: int = dt.now().year
    obj_holidays: HolidayBase = getattr(holidays, user_input[CONF_COUNTRY])(years=year)
    if user_input.get(CONF_PROVINCE):
        obj_holidays = getattr(holidays, user_input[CONF_COUNTRY])(
            subdiv=user_input[CONF_PROVINCE], years=year
        )

    for remove_date in user_input[CONF_REMOVE_HOLIDAYS]:
        if dt.parse_date(remove_date) is None:
            if obj_holidays.get_named(remove_date) == []:
                raise RemoveDatesError("Incorrect date or name")


DATA_SCHEMA_SETUP = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Required(CONF_COUNTRY): SelectSelector(
            SelectSelectorConfig(
                options=list(holidays.list_supported_countries()),
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)

DATA_SCHEMA_OPT = vol.Schema(
    {
        vol.Optional(CONF_EXCLUDES, default=DEFAULT_EXCLUDES): SelectSelector(
            SelectSelectorConfig(
                options=ALLOWED_DAYS, multiple=True, mode=SelectSelectorMode.DROPDOWN
            )
        ),
        vol.Optional(CONF_OFFSET, default=DEFAULT_OFFSET): NumberSelector(
            NumberSelectorConfig(min=-10, max=10, step=1, mode=NumberSelectorMode.BOX)
        ),
        vol.Optional(CONF_WORKDAYS, default=DEFAULT_WORKDAYS): SelectSelector(
            SelectSelectorConfig(
                options=ALLOWED_DAYS, multiple=True, mode=SelectSelectorMode.DROPDOWN
            )
        ),
        vol.Optional(CONF_ADD_HOLIDAYS, default=[]): SelectSelector(
            SelectSelectorConfig(
                options=[],
                multiple=True,
                custom_value=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
        vol.Optional(CONF_REMOVE_HOLIDAYS, default=[]): SelectSelector(
            SelectSelectorConfig(
                options=[],
                multiple=True,
                custom_value=True,
                mode=SelectSelectorMode.DROPDOWN,
            )
        ),
    }
)


class WorkdayConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Workday integration."""

    VERSION = 1

    data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> WorkdayOptionsFlowHandler:
        """Get the options flow for this handler."""
        return WorkdayOptionsFlowHandler(config_entry)

    async def async_step_import(self, config: dict[str, Any]) -> FlowResult:
        """Import a configuration from config.yaml."""

        self._async_abort_entries_match(config)
        return await self.async_step_options(user_input=config)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user initial step."""
        if user_input is not None:
            self.data = user_input
            return await self.async_step_options()
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA_SETUP,
            errors={},
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle remaining flow."""
        errors = {}
        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    validate_custom_dates, {**self.data, **user_input}
                )
            except AddDatesError:
                errors["add_holidays"] = "add_holiday_error"
            except RemoveDatesError:
                errors["remove_holidays"] = "remove_holiday_error"
            except NotImplementedError:
                self.async_abort(reason="incorrect_province")

            if not errors:
                name = self.data.get(CONF_NAME, user_input.get(CONF_NAME))
                return self.async_create_entry(
                    title=name,
                    data={},
                    options={**self.data, **user_input},
                )

        new_schema = await self.hass.async_add_executor_job(
            add_province_to_schema, DATA_SCHEMA_OPT, self.data
        )
        return self.async_show_form(
            step_id="options",
            data_schema=new_schema,
            errors=errors,
        )


class WorkdayOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle Workday options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Workday options."""
        errors = {}

        if user_input is not None:
            try:
                await self.hass.async_add_executor_job(
                    validate_custom_dates, {**self.options, **user_input}
                )
            except AddDatesError:
                errors["add_holidays"] = "add_holiday_error"
            except RemoveDatesError:
                errors["remove_holidays"] = "remove_holiday_error"
            else:
                return self.async_create_entry(
                    title="",
                    data={
                        **self.options,
                        **user_input,
                    },
                )
        schema: vol.Schema = await self.hass.async_add_executor_job(
            add_province_to_schema, DATA_SCHEMA_OPT, self.options
        )
        new_schema = vol.Schema(
            {
                vol.Optional(
                    key.schema,
                    description={"suggested_value": self.options.get(key.schema)},
                ): value
                for key, value in schema.schema.items()
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=new_schema,
            errors=errors,
        )


class AddDatesError(HomeAssistantError):
    """Exception for Adding dates error."""


class RemoveDatesError(HomeAssistantError):
    """Exception for Adding dates error."""

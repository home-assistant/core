"""Adds config flow for Workday integration."""
from __future__ import annotations

from typing import Any

from holidays import HolidayBase, country_holidays, list_supported_countries
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    OptionsFlowWithConfigEntry,
)
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow, FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    CountrySelector,
    CountrySelectorConfig,
    LanguageSelector,
    LanguageSelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
from homeassistant.util import dt as dt_util

from .const import (
    ALLOWED_DAYS,
    CONF_ADD_HOLIDAYS,
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
    LOGGER,
)


def add_province_and_language_to_schema(
    schema: vol.Schema,
    country: str | None,
) -> vol.Schema:
    """Update schema with province from country."""
    if not country:
        return schema

    all_countries = list_supported_countries(include_aliases=False)

    language_schema = {}
    province_schema = {}

    _country = country_holidays(country=country)
    if country_default_language := (_country.default_language):
        selectable_languages = _country.supported_languages
        new_selectable_languages = []
        for lang in selectable_languages:
            new_selectable_languages.append(lang[:2])
        language_schema = {
            vol.Optional(
                CONF_LANGUAGE, default=country_default_language
            ): LanguageSelector(
                LanguageSelectorConfig(languages=new_selectable_languages)
            )
        }

    if provinces := all_countries.get(country):
        province_schema = {
            vol.Optional(CONF_PROVINCE): SelectSelector(
                SelectSelectorConfig(
                    options=provinces,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_PROVINCE,
                )
            ),
        }

    return vol.Schema({**DATA_SCHEMA_OPT.schema, **language_schema, **province_schema})


def _is_valid_date_range(check_date: str, error: type[HomeAssistantError]) -> bool:
    """Validate date range."""
    if check_date.find(",") > 0:
        dates = check_date.split(",", maxsplit=1)
        for date in dates:
            if dt_util.parse_date(date) is None:
                raise error("Incorrect date in range")
        return True
    return False


def validate_custom_dates(user_input: dict[str, Any]) -> None:
    """Validate custom dates for add/remove holidays."""
    for add_date in user_input[CONF_ADD_HOLIDAYS]:
        if (
            not _is_valid_date_range(add_date, AddDateRangeError)
            and dt_util.parse_date(add_date) is None
        ):
            raise AddDatesError("Incorrect date")

    year: int = dt_util.now().year
    if country := user_input.get(CONF_COUNTRY):
        language = user_input.get(CONF_LANGUAGE)
        province = user_input.get(CONF_PROVINCE)
        obj_holidays = country_holidays(
            country=country,
            subdiv=province,
            years=year,
            language=language,
        )
        if (
            supported_languages := obj_holidays.supported_languages
        ) and language == "en":
            for lang in supported_languages:
                if lang.startswith("en"):
                    obj_holidays = country_holidays(
                        country,
                        subdiv=province,
                        years=year,
                        language=lang,
                    )
    else:
        obj_holidays = HolidayBase(years=year)

    for remove_date in user_input[CONF_REMOVE_HOLIDAYS]:
        if (
            not _is_valid_date_range(remove_date, RemoveDateRangeError)
            and dt_util.parse_date(remove_date) is None
            and obj_holidays.get_named(remove_date) == []
        ):
            raise RemoveDatesError("Incorrect date or name")


DATA_SCHEMA_SETUP = vol.Schema(
    {
        vol.Required(CONF_NAME, default=DEFAULT_NAME): TextSelector(),
        vol.Optional(CONF_COUNTRY): CountrySelector(
            CountrySelectorConfig(
                countries=list(list_supported_countries(include_aliases=False)),
            )
        ),
    }
)

DATA_SCHEMA_OPT = vol.Schema(
    {
        vol.Optional(CONF_WORKDAYS, default=DEFAULT_WORKDAYS): SelectSelector(
            SelectSelectorConfig(
                options=ALLOWED_DAYS,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="days",
            )
        ),
        vol.Optional(CONF_EXCLUDES, default=DEFAULT_EXCLUDES): SelectSelector(
            SelectSelectorConfig(
                options=ALLOWED_DAYS,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="days",
            )
        ),
        vol.Optional(CONF_OFFSET, default=DEFAULT_OFFSET): NumberSelector(
            NumberSelectorConfig(min=-10, max=10, step=1, mode=NumberSelectorMode.BOX)
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

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self.data = user_input
            return await self.async_step_options()
        return self.async_show_form(
            step_id="user",
            data_schema=DATA_SCHEMA_SETUP,
            errors=errors,
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle remaining flow."""
        errors: dict[str, str] = {}
        if user_input is not None:
            combined_input: dict[str, Any] = {**self.data, **user_input}

            try:
                await self.hass.async_add_executor_job(
                    validate_custom_dates, combined_input
                )
            except AddDatesError:
                errors["add_holidays"] = "add_holiday_error"
            except AddDateRangeError:
                errors["add_holidays"] = "add_holiday_range_error"
            except RemoveDatesError:
                errors["remove_holidays"] = "remove_holiday_error"
            except RemoveDateRangeError:
                errors["remove_holidays"] = "remove_holiday_range_error"

            abort_match = {
                CONF_COUNTRY: combined_input.get(CONF_COUNTRY),
                CONF_EXCLUDES: combined_input[CONF_EXCLUDES],
                CONF_OFFSET: combined_input[CONF_OFFSET],
                CONF_WORKDAYS: combined_input[CONF_WORKDAYS],
                CONF_ADD_HOLIDAYS: combined_input[CONF_ADD_HOLIDAYS],
                CONF_REMOVE_HOLIDAYS: combined_input[CONF_REMOVE_HOLIDAYS],
                CONF_PROVINCE: combined_input.get(CONF_PROVINCE),
            }
            LOGGER.debug("abort_check in options with %s", combined_input)
            self._async_abort_entries_match(abort_match)

            LOGGER.debug("Errors have occurred %s", errors)
            if not errors:
                LOGGER.debug("No duplicate, no errors, creating entry")
                return self.async_create_entry(
                    title=combined_input[CONF_NAME],
                    data={},
                    options=combined_input,
                )

        schema = await self.hass.async_add_executor_job(
            add_province_and_language_to_schema,
            DATA_SCHEMA_OPT,
            self.data.get(CONF_COUNTRY),
        )
        new_schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(
            step_id="options",
            data_schema=new_schema,
            errors=errors,
            description_placeholders={
                "name": self.data[CONF_NAME],
                "country": self.data.get(CONF_COUNTRY),
            },
        )


class WorkdayOptionsFlowHandler(OptionsFlowWithConfigEntry):
    """Handle Workday options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Workday options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            combined_input: dict[str, Any] = {**self.options, **user_input}
            if CONF_PROVINCE not in user_input:
                # Province not present, delete old value (if present) too
                combined_input.pop(CONF_PROVINCE, None)

            try:
                await self.hass.async_add_executor_job(
                    validate_custom_dates, combined_input
                )
            except AddDatesError:
                errors["add_holidays"] = "add_holiday_error"
            except AddDateRangeError:
                errors["add_holidays"] = "add_holiday_range_error"
            except RemoveDatesError:
                errors["remove_holidays"] = "remove_holiday_error"
            except RemoveDateRangeError:
                errors["remove_holidays"] = "remove_holiday_range_error"
            else:
                LOGGER.debug("abort_check in options with %s", combined_input)
                try:
                    self._async_abort_entries_match(
                        {
                            CONF_COUNTRY: self._config_entry.options.get(CONF_COUNTRY),
                            CONF_EXCLUDES: combined_input[CONF_EXCLUDES],
                            CONF_OFFSET: combined_input[CONF_OFFSET],
                            CONF_WORKDAYS: combined_input[CONF_WORKDAYS],
                            CONF_ADD_HOLIDAYS: combined_input[CONF_ADD_HOLIDAYS],
                            CONF_REMOVE_HOLIDAYS: combined_input[CONF_REMOVE_HOLIDAYS],
                            CONF_PROVINCE: combined_input.get(CONF_PROVINCE),
                        }
                    )
                except AbortFlow as err:
                    errors = {"base": err.reason}
                else:
                    return self.async_create_entry(data=combined_input)

        schema: vol.Schema = await self.hass.async_add_executor_job(
            add_province_and_language_to_schema,
            DATA_SCHEMA_OPT,
            self.options.get(CONF_COUNTRY),
        )

        new_schema = self.add_suggested_values_to_schema(
            schema, user_input or self.options
        )
        LOGGER.debug("Errors have occurred in options %s", errors)
        return self.async_show_form(
            step_id="init",
            data_schema=new_schema,
            errors=errors,
            description_placeholders={
                "name": self.options[CONF_NAME],
                "country": self.options.get(CONF_COUNTRY),
            },
        )


class AddDatesError(HomeAssistantError):
    """Exception for error adding dates."""


class AddDateRangeError(HomeAssistantError):
    """Exception for error adding dates."""


class RemoveDatesError(HomeAssistantError):
    """Exception for error removing dates."""


class RemoveDateRangeError(HomeAssistantError):
    """Exception for error removing dates."""


class CountryNotExist(HomeAssistantError):
    """Exception country does not exist error."""

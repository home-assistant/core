"""Config flow for Holiday integration."""

from __future__ import annotations

from typing import Any

from babel import Locale, UnknownLocaleError
from holidays import PUBLIC, country_holidays, list_supported_countries
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_COUNTRY
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    CountrySelector,
    CountrySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import dt as dt_util

from .const import CONF_CATEGORIES, CONF_PROVINCE, DOMAIN

SUPPORTED_COUNTRIES = list_supported_countries(include_aliases=False)


def get_optional_categories(country: str) -> list[str]:
    """Return the country categories.

    public holidays are always included so they
    don't need to be presented to the user.
    """
    country_data = country_holidays(country, years=dt_util.utcnow().year)
    return [
        category for category in country_data.supported_categories if category != PUBLIC
    ]


def get_options_schema(country: str) -> vol.Schema:
    """Return the options schema."""
    schema = {}
    if provinces := SUPPORTED_COUNTRIES[country]:
        schema[vol.Optional(CONF_PROVINCE)] = SelectSelector(
            SelectSelectorConfig(
                options=provinces,
                mode=SelectSelectorMode.DROPDOWN,
            )
        )
    if categories := get_optional_categories(country):
        schema[vol.Optional(CONF_CATEGORIES)] = SelectSelector(
            SelectSelectorConfig(
                options=categories,
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="categories",
            )
        )
    return vol.Schema(schema)


class HolidayConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Holiday."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> HolidayOptionsFlowHandler:
        """Get the options flow for this handler."""
        return HolidayOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self.data = user_input

            selected_country = user_input[CONF_COUNTRY]

            options_schema = await self.hass.async_add_executor_job(
                get_options_schema, selected_country
            )
            if options_schema.schema:
                return await self.async_step_options()

            self._async_abort_entries_match({CONF_COUNTRY: user_input[CONF_COUNTRY]})

            try:
                locale = Locale.parse(self.hass.config.language, sep="-")
            except UnknownLocaleError:
                # Default to (US) English if language not recognized by babel
                # Mainly an issue with English flavors such as "en-GB"
                locale = Locale("en")
            title = locale.territories[selected_country]
            return self.async_create_entry(title=title, data=user_input)

        user_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_COUNTRY, default=self.hass.config.country
                ): CountrySelector(
                    CountrySelectorConfig(
                        countries=list(SUPPORTED_COUNTRIES),
                    )
                ),
            }
        )

        return self.async_show_form(data_schema=user_schema)

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options step."""
        if user_input is not None:
            country = self.data[CONF_COUNTRY]
            data = {CONF_COUNTRY: country}
            options: dict[str, Any] | None = None
            if province := user_input.get(CONF_PROVINCE):
                data[CONF_PROVINCE] = province
            if categories := user_input.get(CONF_CATEGORIES):
                options = {CONF_CATEGORIES: categories}

            self._async_abort_entries_match({**data, **(options or {})})

            try:
                locale = Locale.parse(self.hass.config.language, sep="-")
            except UnknownLocaleError:
                # Default to (US) English if language not recognized by babel
                # Mainly an issue with English flavors such as "en-GB"
                locale = Locale("en")
            province_str = f", {province}" if province else ""
            name = f"{locale.territories[country]}{province_str}"

            return self.async_create_entry(title=name, data=data, options=options)

        options_schema = await self.hass.async_add_executor_job(
            get_options_schema, self.data[CONF_COUNTRY]
        )
        return self.async_show_form(
            step_id="options",
            data_schema=options_schema,
            description_placeholders={CONF_COUNTRY: self.data[CONF_COUNTRY]},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the re-configuration of the options."""
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            country = reconfigure_entry.data[CONF_COUNTRY]
            data = {CONF_COUNTRY: country}
            options: dict[str, Any] | None = None
            if province := user_input.get(CONF_PROVINCE):
                data[CONF_PROVINCE] = province
            if categories := user_input.get(CONF_CATEGORIES):
                options = {CONF_CATEGORIES: categories}

            self._async_abort_entries_match({**data, **(options or {})})

            try:
                locale = Locale.parse(self.hass.config.language, sep="-")
            except UnknownLocaleError:
                # Default to (US) English if language not recognized by babel
                # Mainly an issue with English flavors such as "en-GB"
                locale = Locale("en")
            province_str = f", {province}" if province else ""
            name = f"{locale.territories[country]}{province_str}"

            if options:
                return self.async_update_reload_and_abort(
                    reconfigure_entry, title=name, data=data, options=options
                )
            return self.async_update_reload_and_abort(
                reconfigure_entry, title=name, data=data
            )

        options_schema = await self.hass.async_add_executor_job(
            get_options_schema, reconfigure_entry.data[CONF_COUNTRY]
        )

        return self.async_show_form(
            data_schema=options_schema,
            description_placeholders={
                CONF_COUNTRY: reconfigure_entry.data[CONF_COUNTRY]
            },
        )


class HolidayOptionsFlowHandler(OptionsFlow):
    """Handle Holiday options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage Holiday options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        categories = await self.hass.async_add_executor_job(
            get_optional_categories, self.config_entry.data[CONF_COUNTRY]
        )
        if not categories:
            return self.async_abort(reason="no_categories")

        schema = vol.Schema(
            {
                vol.Optional(CONF_CATEGORIES): SelectSelector(
                    SelectSelectorConfig(
                        options=categories,
                        multiple=True,
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="categories",
                    )
                )
            }
        )

        return self.async_show_form(
            data_schema=self.add_suggested_values_to_schema(
                schema, self.config_entry.options
            ),
            description_placeholders={
                CONF_COUNTRY: self.config_entry.data[CONF_COUNTRY]
            },
        )

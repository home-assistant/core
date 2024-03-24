"""Config flow for Holiday integration."""

from __future__ import annotations

from typing import Any

from babel import Locale, UnknownLocaleError
from holidays import list_supported_countries
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_COUNTRY
from homeassistant.helpers.selector import (
    CountrySelector,
    CountrySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_PROVINCE, DOMAIN

SUPPORTED_COUNTRIES = list_supported_countries(include_aliases=False)


class HolidayConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Holiday."""

    VERSION = 1
    config_entry: ConfigEntry | None

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if user_input is not None:
            self.data = user_input

            selected_country = user_input[CONF_COUNTRY]

            if SUPPORTED_COUNTRIES[selected_country]:
                return await self.async_step_province()

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

        return self.async_show_form(step_id="user", data_schema=user_schema)

    async def async_step_province(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the province step."""
        if user_input is not None:
            combined_input: dict[str, Any] = {**self.data, **user_input}

            country = combined_input[CONF_COUNTRY]
            province = combined_input.get(CONF_PROVINCE)

            self._async_abort_entries_match(
                {
                    CONF_COUNTRY: country,
                    CONF_PROVINCE: province,
                }
            )

            try:
                locale = Locale.parse(self.hass.config.language, sep="-")
            except UnknownLocaleError:
                # Default to (US) English if language not recognized by babel
                # Mainly an issue with English flavors such as "en-GB"
                locale = Locale("en")
            province_str = f", {province}" if province else ""
            name = f"{locale.territories[country]}{province_str}"

            return self.async_create_entry(title=name, data=combined_input)

        province_schema = vol.Schema(
            {
                vol.Optional(CONF_PROVINCE): SelectSelector(
                    SelectSelectorConfig(
                        options=SUPPORTED_COUNTRIES[self.data[CONF_COUNTRY]],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="province", data_schema=province_schema)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the re-configuration of a province."""
        self.config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reconfigure_confirm()

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the re-configuration of a province."""
        assert self.config_entry

        if user_input is not None:
            combined_input: dict[str, Any] = {**self.config_entry.data, **user_input}

            country = combined_input[CONF_COUNTRY]
            province = combined_input.get(CONF_PROVINCE)

            self._async_abort_entries_match(
                {
                    CONF_COUNTRY: country,
                    CONF_PROVINCE: province,
                }
            )

            try:
                locale = Locale.parse(self.hass.config.language, sep="-")
            except UnknownLocaleError:
                # Default to (US) English if language not recognized by babel
                # Mainly an issue with English flavors such as "en-GB"
                locale = Locale("en")
            province_str = f", {province}" if province else ""
            name = f"{locale.territories[country]}{province_str}"

            return self.async_update_reload_and_abort(
                self.config_entry,
                title=name,
                data=combined_input,
                reason="reconfigure_successful",
            )

        province_schema = vol.Schema(
            {
                vol.Optional(CONF_PROVINCE): SelectSelector(
                    SelectSelectorConfig(
                        options=SUPPORTED_COUNTRIES[
                            self.config_entry.data[CONF_COUNTRY]
                        ],
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="reconfigure_confirm", data_schema=province_schema
        )

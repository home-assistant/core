"""Config flow for Holiday integration."""
from __future__ import annotations

import logging
from typing import Any

from babel import Locale
from holidays import list_supported_countries
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_COUNTRY
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    CountrySelector,
    CountrySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_PROVINCE, DOMAIN

_LOGGER = logging.getLogger(__name__)

SUPPORTED_COUNTRIES = list_supported_countries(include_aliases=False)


class HolidayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Holiday."""

    VERSION = 1

    data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self.data = user_input

            selected_country = self.data[CONF_COUNTRY]

            if SUPPORTED_COUNTRIES[selected_country]:
                return await self.async_step_province()

            locale = Locale(self.hass.config.language)
            title = locale.territories[selected_country]
            return self.async_create_entry(title=title, data=self.data)

        user_schema = vol.Schema(
            {
                vol.Required(
                    CONF_COUNTRY, default=self.hass.config.country
                ): CountrySelector(
                    CountrySelectorConfig(
                        countries=list(SUPPORTED_COUNTRIES),
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=user_schema, errors=errors
        )

    async def async_step_province(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the province step."""
        if user_input is not None:
            combined_input: dict[str, Any] = {**self.data, **user_input}

            locale = Locale(self.hass.config.language)
            name = f"{locale.territories[combined_input[CONF_COUNTRY]]}, {combined_input[CONF_PROVINCE]}"

            return self.async_create_entry(title=name, data=combined_input)

        province_schema = vol.Schema(
            {
                vol.Optional(CONF_PROVINCE): SelectSelector(
                    SelectSelectorConfig(
                        options=SUPPORTED_COUNTRIES[self.data[CONF_COUNTRY]],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_PROVINCE,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="province", data_schema=province_schema)

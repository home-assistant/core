"""Config flow for Holiday integration."""
from __future__ import annotations

import logging
from typing import Any

from holidays import country_holidays, list_supported_countries
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_COUNTRY, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    CountrySelector,
    CountrySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import CONF_PROVINCE, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME): TextSelector(),
        vol.Required(CONF_COUNTRY): CountrySelector(
            CountrySelectorConfig(
                countries=list(list_supported_countries(include_aliases=False)),
            )
        ),
    }
)


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

            if self.data[CONF_COUNTRY]:
                obj_holidays = country_holidays(self.data[CONF_COUNTRY])

                if obj_holidays.subdivisions:
                    return await self.async_step_province()

            return self.async_create_entry(title=self.data[CONF_NAME], data=self.data)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_province(self, user_input=None) -> FlowResult:
        """Handle the province step."""
        if user_input is not None:
            combined_input: dict[str, Any] = {**self.data, **user_input}
            return self.async_create_entry(
                title=self.data[CONF_NAME], data=combined_input
            )

        all_countries = list_supported_countries(include_aliases=False)

        province_schema = vol.Schema(
            {
                vol.Optional(CONF_PROVINCE): SelectSelector(
                    SelectSelectorConfig(
                        options=all_countries[self.data[CONF_COUNTRY]],
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key=CONF_PROVINCE,
                    )
                ),
            }
        )

        return self.async_show_form(step_id="province", data_schema=province_schema)

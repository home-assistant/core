"""Repairs for the Holiday integration."""

from typing import Any

import probatio

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_COUNTRY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import CountrySelector, CountrySelectorConfig

from .config_flow import SUPPORTED_COUNTRIES, get_entry_name, get_options_schema
from .const import CONF_CATEGORIES, CONF_PROVINCE, ISSUE_UNSUPPORTED_COUNTRY


class UnsupportedConfigurationFixFlow(RepairsFlow):
    """Handler for fixing a configuration the holidays library no longer supports."""

    def __init__(self, entry: ConfigEntry, issue: str) -> None:
        """Create flow."""
        self.entry = entry
        self.issue = issue
        self.country: str = entry.data[CONF_COUNTRY]
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        if self.issue == ISSUE_UNSUPPORTED_COUNTRY:
            return await self.async_step_country()
        return await self.async_step_options()

    async def async_step_country(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the country step of a fix flow."""
        if user_input is not None:
            self.country = user_input[CONF_COUNTRY]
            return await self.async_step_options()

        return self.async_show_form(
            step_id="country",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_COUNTRY): CountrySelector(
                        CountrySelectorConfig(countries=list(SUPPORTED_COUNTRIES))
                    )
                }
            ),
            description_placeholders=self._placeholders(),
        )

    async def async_step_options(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the province and categories step of a fix flow."""
        if user_input is not None:
            data = {CONF_COUNTRY: self.country}
            options: dict[str, Any] = {}
            if province := user_input.get(CONF_PROVINCE):
                data[CONF_PROVINCE] = province
            if categories := user_input.get(CONF_CATEGORIES):
                options[CONF_CATEGORIES] = categories
            title = await self.hass.async_add_executor_job(
                get_entry_name, self.hass.config.language, self.country, province
            )
            self.hass.config_entries.async_update_entry(
                self.entry, title=title, data=data, options=options
            )
            await self.hass.config_entries.async_reload(self.entry.entry_id)
            return self.async_create_entry(data={})

        options_schema = await self.hass.async_add_executor_job(
            get_options_schema, self.country
        )
        return self.async_show_form(
            step_id="options",
            data_schema=options_schema,
            description_placeholders={
                **self._placeholders(),
                "country": self.country,
            },
        )

    def _placeholders(self) -> dict[str, str]:
        """Return the placeholders of the configuration that is no longer supported."""
        return {
            "title": self.entry.title,
            "country": self.entry.data[CONF_COUNTRY],
            "province": self.entry.data.get(CONF_PROVINCE) or "",
            "categories": ", ".join(self.entry.options.get(CONF_CATEGORIES, [])),
        }


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create flow."""
    if data and (entry := hass.config_entries.async_get_entry(data["entry_id"])):
        return UnsupportedConfigurationFixFlow(entry, data["issue"])
    return ConfirmRepairFlow()

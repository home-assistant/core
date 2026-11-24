"""Repairs platform for the Workday integration."""

from typing import Any, cast

from holidays import list_supported_countries
import probatio

from homeassistant.components.repairs import (
    ConfirmRepairFlow,
    RepairsFlow,
    RepairsFlowResult,
)
from homeassistant.const import CONF_COUNTRY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from . import WorkdayConfigEntry
from .config_flow import validate_custom_dates
from .const import (
    CONF_PROVINCE,
    CONF_REMOVE_HOLIDAYS,
    SECTION_COUNTRY_SETTINGS,
    SECTION_CUSTOM_HOLIDAYS,
)


class CountryFixFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, entry: WorkdayConfigEntry, country: str | None) -> None:
        """Create flow."""
        self.entry = entry
        self.country: str | None = country
        super().__init__()

    def _options_with_country(
        self, country: str | None, province: str | None
    ) -> dict[str, Any]:
        """Return the entry options with a new country and province."""
        options = dict(self.entry.options)
        options[CONF_COUNTRY] = country
        options[SECTION_COUNTRY_SETTINGS] = {
            **options.get(SECTION_COUNTRY_SETTINGS, {}),
            CONF_PROVINCE: province,
        }
        return options

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        if self.country:
            return await self.async_step_province()
        return await self.async_step_country()

    async def async_step_country(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the country step of a fix flow."""
        if user_input is not None:
            all_countries = list_supported_countries(include_aliases=False)
            if not all_countries[user_input[CONF_COUNTRY]]:
                self.hass.config_entries.async_update_entry(
                    self.entry,
                    options=self._options_with_country(user_input[CONF_COUNTRY], None),
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_create_entry(data={})
            self.country = user_input[CONF_COUNTRY]
            return await self.async_step_province()

        return self.async_show_form(
            step_id="country",
            data_schema=probatio.Schema(
                {
                    probatio.Required(CONF_COUNTRY): SelectSelector(
                        SelectSelectorConfig(
                            options=sorted(
                                list_supported_countries(include_aliases=False)
                            ),
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
            description_placeholders={"title": self.entry.title},
        )

    async def async_step_province(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the province step of a fix flow."""
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self.entry,
                options=self._options_with_country(
                    self.country, user_input.get(CONF_PROVINCE)
                ),
            )
            await self.hass.config_entries.async_reload(self.entry.entry_id)
            return self.async_create_entry(data={})

        assert self.country
        country_provinces = list_supported_countries(include_aliases=False)[
            self.country
        ]
        return self.async_show_form(
            step_id="province",
            data_schema=probatio.Schema(
                {
                    probatio.Optional(CONF_PROVINCE): SelectSelector(
                        SelectSelectorConfig(
                            options=country_provinces,
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key=CONF_PROVINCE,
                        )
                    ),
                }
            ),
            description_placeholders={
                "country": self.country,
                "title": self.entry.title,
            },
        )


class HolidayFixFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(
        self, entry: WorkdayConfigEntry, country: str | None, named_holiday: str
    ) -> None:
        """Create flow."""
        self.entry = entry
        self.country: str | None = country
        self.named_holiday: str = named_holiday
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_fix_remove_holiday()

    async def async_step_fix_remove_holiday(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the options step of a fix flow."""
        errors: dict[str, str] = {}
        if user_input:
            options = dict(self.entry.options)
            new_options = {
                **options,
                SECTION_CUSTOM_HOLIDAYS: {
                    **options[SECTION_CUSTOM_HOLIDAYS],
                    **user_input,
                },
            }
            try:
                await self.hass.async_add_executor_job(
                    validate_custom_dates, new_options
                )
            except Exception:  # noqa: BLE001
                errors["remove_holidays"] = "remove_holiday_error"
            else:
                self.hass.config_entries.async_update_entry(
                    self.entry, options=new_options
                )
                await self.hass.config_entries.async_reload(self.entry.entry_id)
                return self.async_create_entry(data={})

        remove_holidays = self.entry.options[SECTION_CUSTOM_HOLIDAYS][
            CONF_REMOVE_HOLIDAYS
        ]
        removed_named_holiday = [
            value for value in remove_holidays if value != self.named_holiday
        ]
        new_schema = self.add_suggested_values_to_schema(
            probatio.Schema(
                {
                    probatio.Optional(CONF_REMOVE_HOLIDAYS, default=[]): SelectSelector(
                        SelectSelectorConfig(
                            options=[],
                            multiple=True,
                            custom_value=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
            {CONF_REMOVE_HOLIDAYS: removed_named_holiday},
        )
        return self.async_show_form(
            step_id="fix_remove_holiday",
            data_schema=new_schema,
            description_placeholders={
                "country": self.country or "-",
                "remove_holidays": self.named_holiday,
                "title": self.entry.title,
            },
            errors=errors,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, Any] | None,
) -> RepairsFlow:
    """Create flow."""
    entry = None
    if data and (entry_id := data.get("entry_id")):
        entry_id = cast(str, entry_id)
        entry = hass.config_entries.async_get_entry(entry_id)

    if data and (holiday := data.get("named_holiday")) and entry:
        # Bad named holiday in configuration
        return HolidayFixFlow(entry, data.get("country"), holiday)

    if data and entry:
        # Country or province does not exist
        return CountryFixFlow(entry, data.get("country"))

    return ConfirmRepairFlow()

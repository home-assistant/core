"""Config flow for the School Holiday integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_COUNTRY, CONF_REGION
from homeassistant.core import callback
from homeassistant.generated.languages import LANGUAGES
from homeassistant.helpers import translation
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_CALENDAR_NAME, CONF_SENSOR_NAME, COUNTRIES, DOMAIN, REGIONS
from .utils import get_device_name


class SchoolHolidayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for School Holiday."""

    VERSION = 1
    MINOR_VERSION = 0

    def __init__(self) -> None:
        """Initialize the config flow."""
        super().__init__()
        self._sensor_name: str = ""
        self._country: str = ""
        self._region: str = ""
        self._calendar_name: str = ""
        self._translations: dict[str, Any] = {}

    @callback
    def _get_default(self, entity_type: str, fallback: str) -> str:
        """Get translated default entity name."""
        entity_key = f"component.{DOMAIN}.entity.{entity_type}.name"
        return str(self._translations.get(entity_key, fallback))

    @callback
    def _get_translation_language(self) -> str:
        """Return normalized language code for translation files."""
        language = self.hass.config.language

        if language in LANGUAGES:
            return language

        parts = language.split("-")
        primary = parts[0]
        if primary in LANGUAGES:
            return primary

        secondary = parts[-1]
        if secondary in LANGUAGES:
            return secondary

        return primary

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Enter binary sensor name and select country."""
        errors: dict[str, str] = {}

        language = self._get_translation_language()

        # Load config translations.
        self._translations = await translation.async_get_translations(
            self.hass,
            language,
            "config",
            {DOMAIN},
        )

        # Load entity translations for default names.
        self._translations.update(
            await translation.async_get_translations(
                self.hass,
                language,
                "entity",
                {DOMAIN},
            )
        )

        if user_input is not None:
            sensor_name = user_input.get(CONF_SENSOR_NAME, "").strip()
            if not sensor_name:
                errors[CONF_SENSOR_NAME] = "required"

            country = user_input.get(CONF_COUNTRY)
            if not country:
                errors[CONF_COUNTRY] = "required"

            if not errors:
                self._sensor_name = str(sensor_name)
                self._country = str(country)
                return await self.async_step_region()

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SENSOR_NAME,
                    default=self._get_default(
                        "binary_sensor.school_holiday_sensor", "School Holiday Sensor"
                    ),
                ): str,
                vol.Required(CONF_COUNTRY): SelectSelector(
                    SelectSelectorConfig(
                        options=COUNTRIES,
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key="country",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            description_placeholders={},
            errors=errors,
        )

    async def async_step_region(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Select region for the selected country."""
        errors: dict[str, str] = {}
        regions = REGIONS.get(self._country, [])

        if user_input is not None:
            region = user_input.get(CONF_REGION)
            if not region:
                errors[CONF_REGION] = "required"
            elif region not in regions:
                errors[CONF_REGION] = "invalid"

            if not errors:
                # Assert that region is a string for type safety.
                if TYPE_CHECKING:
                    assert isinstance(region, str)
                self._region = region
                return await self.async_step_calendar()

        data_schema = vol.Schema(
            {
                vol.Required(CONF_REGION): SelectSelector(
                    SelectSelectorConfig(
                        options=regions,
                        mode=SelectSelectorMode.DROPDOWN,
                        translation_key=f"region_{self._country}",
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="region",
            data_schema=data_schema,
            description_placeholders={},
            errors=errors,
        )

    async def async_step_calendar(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Enter calendar name."""
        errors: dict[str, str] = {}

        if user_input is not None:
            calendar_name = user_input.get(CONF_CALENDAR_NAME, "").strip()
            if not calendar_name:
                errors[CONF_CALENDAR_NAME] = "required"

            if not errors:
                # Prevent duplicate configurations for the same country/region.
                self._async_abort_entries_match(
                    {
                        CONF_COUNTRY: self._country,
                        CONF_REGION: self._region,
                    }
                )

                self._calendar_name = calendar_name

                return self.async_create_entry(
                    title=get_device_name(self._country, self._region),
                    data={
                        CONF_SENSOR_NAME: self._sensor_name,
                        CONF_COUNTRY: self._country,
                        CONF_REGION: self._region,
                        CONF_CALENDAR_NAME: self._calendar_name,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_CALENDAR_NAME,
                    default=self._get_default(
                        "calendar.school_holiday_calendar", "School Holiday Calendar"
                    ),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="calendar",
            data_schema=data_schema,
            description_placeholders={},
            errors=errors,
        )

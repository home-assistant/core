"""Config flow for the MeteoAlarm integration."""

from typing import Any, override

from meteoalarmapi import Meteoalert, ServerError, UnexpectedError, WrongCountry
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE, CONF_NAME
from homeassistant.helpers.selector import (
    CountrySelector,
    CountrySelectorConfig,
    LanguageSelector,
)

from .const import CONF_PROVINCE, COUNTRIES, DOMAIN


def _check_feed(data: dict[str, Any]) -> None:
    """Fetch the country's feed once, raising the library's errors."""
    Meteoalert(data[CONF_COUNTRY], data[CONF_PROVINCE], data[CONF_LANGUAGE]).get_alert()


def _unique_id(data: dict[str, Any]) -> str:
    """Return the unique ID for a region, the same however it was added."""
    return f"{data[CONF_COUNTRY]}_{data[CONF_PROVINCE]}_{data[CONF_LANGUAGE]}".lower()


class MeteoAlarmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MeteoAlarm."""

    VERSION = 1

    async def _async_validate(self, data: dict[str, Any]) -> str | None:
        """Check the country's feed, returning an error key or None."""
        try:
            await self.hass.async_add_executor_job(_check_feed, data)
        except WrongCountry:
            return "invalid_country"
        except ServerError, UnexpectedError:
            return "cannot_connect"
        return None

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # The country selector gives the ISO code; the feed uses a name.
            data = {
                CONF_COUNTRY: COUNTRIES[user_input[CONF_COUNTRY]],
                CONF_PROVINCE: user_input[CONF_PROVINCE],
                CONF_LANGUAGE: user_input[CONF_LANGUAGE],
            }
            await self.async_set_unique_id(_unique_id(data))
            self._abort_if_unique_id_configured()

            if error := await self._async_validate(data):
                errors["base"] = error
            else:
                return self.async_create_entry(title=data[CONF_PROVINCE], data=data)

        schema = probatio.Schema(
            {
                probatio.Required(CONF_COUNTRY): CountrySelector(
                    CountrySelectorConfig(countries=list(COUNTRIES))
                ),
                probatio.Required(CONF_PROVINCE): str,
                probatio.Required(
                    CONF_LANGUAGE, default=self.hass.config.language
                ): LanguageSelector(),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a region from the legacy YAML configuration.

        The entry is titled with the YAML name, so the entity gets the entity
        ID it had in YAML (binary_sensor.meteoalarm by default).
        """
        data = {
            CONF_COUNTRY: import_data[CONF_COUNTRY].lower(),
            CONF_PROVINCE: import_data[CONF_PROVINCE],
            CONF_LANGUAGE: import_data[CONF_LANGUAGE],
        }
        await self.async_set_unique_id(_unique_id(data))
        self._abort_if_unique_id_configured()

        if error := await self._async_validate(data):
            return self.async_abort(reason=error)

        return self.async_create_entry(title=import_data[CONF_NAME], data=data)

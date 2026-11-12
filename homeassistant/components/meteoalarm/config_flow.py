"""Config flow for the MeteoAlarm integration."""

from typing import Any, override

from meteoalarmapi import Meteoalert, ServerError, UnexpectedError, WrongCountry
import probatio

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_COUNTRY, CONF_LANGUAGE, CONF_NAME
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import CONF_PROVINCE, COUNTRIES, DEFAULT_LANGUAGE, DOMAIN

STEP_USER_DATA_SCHEMA = probatio.Schema(
    {
        probatio.Required(CONF_COUNTRY): SelectSelector(
            SelectSelectorConfig(
                options=COUNTRIES,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key=CONF_COUNTRY,
                sort=True,
            )
        ),
        probatio.Required(CONF_PROVINCE): str,
        probatio.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): str,
    }
)


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
            await self.async_set_unique_id(_unique_id(user_input))
            self._abort_if_unique_id_configured()

            if error := await self._async_validate(user_input):
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=user_input[CONF_PROVINCE],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA, user_input
            ),
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import a region from the legacy YAML configuration.

        The entry is titled with the YAML name, so the entity keeps the entity
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

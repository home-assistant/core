"""MeteoAlarm config flow."""

from typing import Any

from meteoalertapi import Meteoalert
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_COUNTRY,
    CONF_LANGUAGE,
    CONF_PROVINCE,
    DEFAULT_COUNTRY,
    DOMAIN,
    LOGGER,
    SUPPORTED_COUNTRIES,
)

SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COUNTRY, default=DEFAULT_COUNTRY): selector.CountrySelector(
            selector.CountrySelectorConfig(countries=list(SUPPORTED_COUNTRIES.keys()))
        ),
        vol.Required(CONF_PROVINCE): cv.string,
        vol.Optional(CONF_LANGUAGE, default="en"): cv.string,
    }
)


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate user input."""

    meteo = Meteoalert(data[CONF_COUNTRY], data[CONF_PROVINCE], data[CONF_LANGUAGE])
    result = meteo.get_alert()
    if not result:
        raise CannotConnect

    return {
        "title": f"Alerts for {data[CONF_PROVINCE]}({data[CONF_COUNTRY]}) in {data[CONF_LANGUAGE]}"
    }


class MeteoAlarmConfigFlow(ConfigFlow, domain=DOMAIN):
    """MeteoAlarm config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle config flow initiated by the user."""
        errors = {}
        if user_input:
            self._async_abort_entries_match(
                {
                    CONF_COUNTRY: SUPPORTED_COUNTRIES.get(
                        user_input[CONF_COUNTRY], DEFAULT_COUNTRY
                    ),
                    CONF_PROVINCE: user_input[CONF_PROVINCE],
                    CONF_LANGUAGE: user_input[CONF_LANGUAGE],
                }
            )

            try:
                info = validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unknown exception")
                errors["base"] = "unknown"
            else:
                user_input[CONF_COUNTRY] = SUPPORTED_COUNTRIES.get(
                    user_input[CONF_COUNTRY]
                )
                await self.async_set_unique_id(
                    f"{user_input[CONF_COUNTRY]}_{user_input[CONF_PROVINCE]}_{user_input[CONF_LANGUAGE]}"
                )
                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=SCHEMA,
            errors=errors,
        )

    async def async_step_import(
        self, import_config: dict[str, Any]
    ) -> ConfigFlowResult:
        """Attempt to import the existing configuration from yaml."""
        self._async_abort_entries_match(
            {
                CONF_COUNTRY: SUPPORTED_COUNTRIES.get(
                    import_config[CONF_COUNTRY], DEFAULT_COUNTRY
                ),
                CONF_PROVINCE: import_config[CONF_PROVINCE],
                CONF_LANGUAGE: import_config[CONF_LANGUAGE],
            }
        )

        try:
            info = validate_input(self.hass, import_config)
        except CannotConnect:
            return self.async_abort(reason="cannot_connect")
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unknown exception while importing")
            return self.async_abort(reason="unknown")

        await self.async_set_unique_id(
            f"{import_config[CONF_COUNTRY]}_{import_config[CONF_PROVINCE]}_{import_config[CONF_LANGUAGE]}"
        )
        return self.async_create_entry(
            title=info["title"],
            data={
                CONF_COUNTRY: SUPPORTED_COUNTRIES.get(
                    import_config[CONF_COUNTRY], DEFAULT_COUNTRY
                ),
                CONF_PROVINCE: import_config[CONF_PROVINCE],
                CONF_LANGUAGE: import_config[CONF_LANGUAGE],
            },
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

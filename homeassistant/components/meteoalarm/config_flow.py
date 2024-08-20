"""MeteoAlarm config flow."""

from typing import Any

from meteoalertapi import Meteoalert
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_NAME
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


class MeteoAlarmConfigFlow(ConfigFlow, domain=DOMAIN):
    """MeteoAlarm config flow."""

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
                Meteoalert(CONF_COUNTRY, CONF_PROVINCE, CONF_LANGUAGE)

            except KeyError:
                LOGGER.error("Wrong country digits or province name")
                errors["base"] = "wrong_country_or_province"
            except Exception:  # noqa: BLE001
                LOGGER.exception("Unknown exception")
                errors["base"] = "unknown"
            else:
                user_input[CONF_COUNTRY] = SUPPORTED_COUNTRIES.get(
                    user_input[CONF_COUNTRY], DEFAULT_COUNTRY
                )
                return self.async_create_entry(
                    title=DOMAIN,
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
            Meteoalert(
                SUPPORTED_COUNTRIES.get(import_config[CONF_COUNTRY], DEFAULT_COUNTRY),
                import_config[CONF_PROVINCE],
                import_config[CONF_LANGUAGE],
            )

        except KeyError:
            LOGGER.error("Wrong country digits or province name while importing")
            return self.async_abort(reason="wrong_country_or_province")
        except Exception:  # noqa: BLE001
            LOGGER.exception("Unknown exception while importing")
            return self.async_abort(reason="unknown")

        return self.async_create_entry(
            title=import_config.get(CONF_NAME, DOMAIN),
            data={
                CONF_COUNTRY: SUPPORTED_COUNTRIES.get(
                    import_config[CONF_COUNTRY], DEFAULT_COUNTRY
                ),
                CONF_PROVINCE: import_config[CONF_PROVINCE],
                CONF_LANGUAGE: import_config[CONF_LANGUAGE],
            },
        )

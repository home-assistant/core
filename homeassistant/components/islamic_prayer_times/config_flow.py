"""Config flow for Islamic Prayer Times integration."""
from __future__ import annotations

from typing import Any

from prayer_times_calculator import InvalidResponseError, PrayerTimesCalculator
from requests.exceptions import ConnectionError as ConnError
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LOCATION, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import (
    LocationSelector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)
import homeassistant.util.dt as dt_util

from .const import (
    CALC_METHODS,
    CONF_CALC_METHOD,
    CONF_LAT_ADJ_METHOD,
    CONF_MIDNIGHT_MODE,
    CONF_SCHOOL,
    DEFAULT_CALC_METHOD,
    DEFAULT_LAT_ADJ_METHOD,
    DEFAULT_MIDNIGHT_MODE,
    DEFAULT_SCHOOL,
    DOMAIN,
    LAT_ADJ_METHODS,
    MIDNIGHT_MODES,
    NAME,
    SCHOOLS,
)


async def async_validate_location(
    hass: HomeAssistant, lon: float, lat: float
) -> dict[str, str]:
    """Check if the selected location is valid."""
    errors = {}
    calc = PrayerTimesCalculator(
        latitude=lat,
        longitude=lon,
        calculation_method=DEFAULT_CALC_METHOD,
        date=str(dt_util.now().date()),
    )
    try:
        await hass.async_add_executor_job(calc.fetch_prayer_times)
    except InvalidResponseError:
        errors["base"] = "invalid_location"
    except ConnError:
        errors["base"] = "conn_error"
    return errors


class IslamicPrayerFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Islamic Prayer config flow."""

    VERSION = 1
    MINOR_VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> IslamicPrayerOptionsFlowHandler:
        """Get the options flow for this handler."""
        return IslamicPrayerOptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors = {}

        if user_input is not None:
            lat: float = user_input[CONF_LOCATION][CONF_LATITUDE]
            lon: float = user_input[CONF_LOCATION][CONF_LONGITUDE]
            await self.async_set_unique_id(f"{lat}-{lon}")
            self._abort_if_unique_id_configured()

            if not (errors := await async_validate_location(self.hass, lat, lon)):
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_LATITUDE: lat,
                        CONF_LONGITUDE: lon,
                    },
                )

        home_location = {
            CONF_LATITUDE: self.hass.config.latitude,
            CONF_LONGITUDE: self.hass.config.longitude,
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=NAME): TextSelector(),
                    vol.Required(
                        CONF_LOCATION, default=home_location
                    ): LocationSelector(),
                }
            ),
            errors=errors,
        )


class IslamicPrayerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Islamic Prayer client options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = {
            vol.Optional(
                CONF_CALC_METHOD,
                default=self.config_entry.options.get(
                    CONF_CALC_METHOD, DEFAULT_CALC_METHOD
                ),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=CALC_METHODS,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_CALC_METHOD,
                )
            ),
            vol.Optional(
                CONF_LAT_ADJ_METHOD,
                default=self.config_entry.options.get(
                    CONF_LAT_ADJ_METHOD, DEFAULT_LAT_ADJ_METHOD
                ),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=LAT_ADJ_METHODS,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_LAT_ADJ_METHOD,
                )
            ),
            vol.Optional(
                CONF_MIDNIGHT_MODE,
                default=self.config_entry.options.get(
                    CONF_MIDNIGHT_MODE, DEFAULT_MIDNIGHT_MODE
                ),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=MIDNIGHT_MODES,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_MIDNIGHT_MODE,
                )
            ),
            vol.Optional(
                CONF_SCHOOL,
                default=self.config_entry.options.get(CONF_SCHOOL, DEFAULT_SCHOOL),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=SCHOOLS,
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_SCHOOL,
                )
            ),
        }

        return self.async_show_form(step_id="init", data_schema=vol.Schema(options))
